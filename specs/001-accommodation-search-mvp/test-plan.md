# Test Plan: Accommodation Search MVP

**Feature**: `001-accommodation-search-mvp`  
**Branch**: `001-accommodation-search-mvp`  
**Author**: autotester  
**Date**: 2026-07-19  
**Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md) | **Tasks**: [tasks.md](tasks.md)

---

## 1. Scope

This plan covers all automated and manual verification for the TravelSearch MVP:

- Authentication and session management
- Multi-provider accommodation search
- Tracked search background monitoring
- Tracked property via Telegram bot
- Account and Telegram linking
- Cross-cutting: data isolation, security, deployment gate

**Out of scope**: Live Booking/Airbnb scraping in CI; live Telegram API calls in CI; flight provider (explicitly excluded from MVP).

---

## 2. Test Levels

| Level | Tool | When |
|-------|------|------|
| Unit | pytest + pytest-asyncio | Every commit |
| Integration | pytest + AsyncClient + mocked external deps | Every PR |
| Contract | pytest + recorded fixtures | Every PR |
| Frontend component | Vitest + @testing-library/react | Every PR |
| System gate | `docker compose up` + smoke-test.sh | Pre-merge to main |
| Security negative | pytest (subset of integration) | Every PR |
| Manual exploratory | Charter below | Pre-release |

**CI gates** (block merge):
1. Unit + integration + contract tests: 100% pass, no flaky.
2. mypy strict + ruff clean.
3. tsc --noEmit clean.
4. Safe-discard invariant test (see §4.6) — hard release gate.

---

## 3. Test Infrastructure Requirements (tasks T028, T029)

### Backend (`backend/tests/conftest.py`)
- `pytest-asyncio` with `asyncio_mode = "auto"`.
- `async_client` fixture: `httpx.AsyncClient` against the FastAPI app.
- `db_session` fixture: creates tables, yields session, rolls back after each test (never commits).
- `redis_mock` fixture: `fakeredis.aioredis` instance injected via DI override.
- `DATABASE_URL_TEST` env var pointing to a throwaway test schema.
- `override_current_user(user)` helper to inject a pre-built User into `get_current_user`.
- Provider fixture factory: returns a `MagicMock` implementing `Provider` ABC with controllable `SearchResult`.
- Notifier fixture: `MagicMock` implementing `Notifier` ABC; captures `send()` calls.

### Frontend (`frontend/tests/`)
- Vitest config in `vite.config.ts`.
- `@testing-library/react` + `msw` for API mocking.
- `setup.ts` with global mocks for `window.location`, `fetch`.

---

## 4. Test Scenarios

### 4.1 Tracking Service Unit Tests (T062, maps to FR-009, FR-016)

**File**: `backend/tests/unit/test_tracking_service.py`

#### 4.1.1 `create_tracked_search`

| ID | Description | Input | Expected |
|----|-------------|-------|----------|
| TS-U-01 | Create first tracked search | valid `search_id`, `interval_hours=6` | Returns `TrackedSearch`, row in DB |
| TS-U-02 | Duplicate: same user + same search | same call twice | Returns existing `TrackedSearch`, no duplicate row, interval updated |
| TS-U-03 | Invalid interval (not in {6,12,24,48}) | `interval_hours=7` | Raises `ValidationError` / returns 422 |
| TS-U-04 | Limit exceeded (11th tracked search) | create 10, then attempt 11th | Raises `TrackingLimitExceededError` |
| TS-U-05 | Telegram not linked — warning returned | user.telegram_chat_id is None | Returns TrackedSearch + `no_telegram_warning=True` |

#### 4.1.2 `remove_tracked_search`

| ID | Description | Input | Expected |
|----|-------------|-------|----------|
| TS-U-06 | Remove existing | valid id owned by user | Row soft-deleted / removed; returns 200/204 |
| TS-U-07 | Remove non-existent | unknown id | Raises 404 |
| TS-U-08 | Remove another user's search | id owned by user B, called by user A | Raises 404 (no information leak) |

#### 4.1.3 `create_tracked_property`

| ID | Description | Input | Expected |
|----|-------------|-------|----------|
| TS-U-09 | Create first tracked property | valid URL + dates | Returns `TrackedProperty` |
| TS-U-10 | Duplicate (same user, property, dates) | same call twice | Returns existing, no duplicate |
| TS-U-11 | Limit exceeded (21st tracked property) | create 20, then attempt 21st | Raises `TrackingLimitExceededError` |
| TS-U-12 | URL with no parseable dates | Booking URL without check-in param | Returns error asking for dates |
| TS-U-13 | Unrecognized URL (not Booking or Airbnb) | `https://tripadvisor.com/...` | Returns error |

#### 4.1.4 `remove_tracked_property`

| ID | Description | Input | Expected |
|----|-------------|-------|----------|
| TS-U-14 | Remove existing | valid id owned by user | Removed |
| TS-U-15 | Remove non-existent | unknown id | 404 |

---

### 4.2 Diff Logic Unit Tests (T063, maps to FR-005, FR-013)

**File**: `backend/tests/unit/test_search_diff.py`

| ID | Description | Input | Expected |
|----|-------------|-------|----------|
| DL-U-01 | Empty baseline — all current listings are new | seen={}, current=[A,B] | Returns `[NewListing(A), NewListing(B)]` |
| DL-U-02 | All seen — no new listings | seen={A,B}, current=[A,B] | Returns `[]` |
| DL-U-03 | No new listings | seen={A,B,C}, current=[A,B] | Returns `[]` (C disappeared — no event) |
| DL-U-04 | Price drop below `min_price_seen` | A.min_price=100, current_price=80 | Returns `[PriceDrop(A, old=100, new=80)]` |
| DL-U-05 | Price increase above `min_price_seen` | A.min_price=100, current_price=120 | Returns `[]` |
| DL-U-06 | Price equal to `min_price_seen` | A.min_price=100, current_price=100 | Returns `[]` (no drop) |
| DL-U-07 | Empty current listings — safe discard | current=[] | Returns `[]` regardless of seen |
| DL-U-08 | Provider error in one of N results | SearchResult with status=BLOCKED | Worker discards cycle — diff never called |
| DL-U-09 | Mixed: new + price-drop in same cycle | seen={A.min=100}, current=[A@80, B] | Returns `[PriceDrop(A), NewListing(B)]` |

---

### 4.3 API Integration Tests with Mocked Telegram (T042, T064, T079, T091)

**Files**: `backend/tests/integration/test_*.py`  
**Setup**: `AsyncClient`, real PostgreSQL (test schema), `fakeredis`, all provider calls mocked, all Telegram API calls mocked via `httpx` mock transport.

#### Auth (maps to FR-001, SC-001)

| ID | Endpoint | Scenario | Expected |
|----|----------|----------|----------|
| API-A-01 | POST /auth/login | Valid credentials | 200 + access_token + HttpOnly refresh cookie |
| API-A-02 | POST /auth/login | Wrong password | 401 Problem Details |
| API-A-03 | POST /auth/login | Unknown email | 401 (no distinction) |
| API-A-04 | POST /auth/refresh | Valid cookie | 200 + new access_token |
| API-A-05 | POST /auth/refresh | Revoked/missing cookie | 401 |
| API-A-06 | POST /auth/logout | Valid session | 204 + cookie cleared |
| API-A-07 | Any protected endpoint | No Authorization header | 401 |
| API-A-08 | Any protected endpoint | Expired access token | 401 |

#### Search (maps to FR-002, FR-003, FR-004, SC-001, SC-002)

| ID | Endpoint | Scenario | Expected |
|----|----------|----------|----------|
| API-S-01 | POST /search | Valid request, both providers | 202 + search_id |
| API-S-02 | GET /search/{id}/status | Poll while running | 200 + per-provider status |
| API-S-03 | GET /search/{id}/results | Complete search | 200 + merged listing rows from both providers |
| API-S-04 | GET /search/{id}/results | Sort by price asc | 200 + correctly ordered results |
| API-S-05 | GET /search/{id}/export.csv | Complete search | 200 Content-Type: text/csv, correct row count |
| API-S-06 | POST /search | One provider returns BLOCKED | 202 → results show working provider only + failure notice |
| API-S-07 | GET /search/{id}/results | Zero results both providers | 200 + empty array (no error) |
| API-S-08 | POST /search | Unauthenticated | 401 |

#### Tracked Search (maps to FR-005, FR-006, FR-009, FR-016)

| ID | Endpoint | Scenario | Expected |
|----|----------|----------|----------|
| API-TS-01 | POST /tracked-searches | Valid request, interval=6 | 201 + TrackedSearch |
| API-TS-02 | POST /tracked-searches | interval=7 (invalid) | 422 Problem Details |
| API-TS-03 | POST /tracked-searches | 11th search (limit exceeded) | 422 + clear error message |
| API-TS-04 | POST /tracked-searches | Duplicate (same search) | 200 + existing TrackedSearch, interval updated |
| API-TS-05 | GET /tracked-searches | List owned searches | 200 + only caller's rows |
| API-TS-06 | DELETE /tracked-searches/{id} | Valid | 204 |
| API-TS-07 | DELETE /tracked-searches/{id} | Not found | 404 |

#### Tracked Property (maps to FR-007, FR-008, FR-016)

| ID | Endpoint | Scenario | Expected |
|----|----------|----------|----------|
| API-TP-01 | POST /tracked-properties | Valid | 201 + TrackedProperty |
| API-TP-02 | POST /tracked-properties | 21st property | 422 + limit message |
| API-TP-03 | POST /tracked-properties | Duplicate | 200 + existing |
| API-TP-04 | GET /tracked-properties | List | 200 + only caller's |
| API-TP-05 | DELETE /tracked-properties/{id} | Valid | 204 |

#### Notifications (maps to FR-011)

| ID | Endpoint | Scenario | Expected |
|----|----------|----------|----------|
| API-N-01 | GET /notifications | No history | 200 + empty array |
| API-N-02 | GET /notifications | After tracked search fires | 200 + rows with price_before/after |
| API-N-03 | GET /notifications | Filter by type=price_drop | 200 + only price_drop rows |

#### Telegram Linking (maps to FR-012)

| ID | Endpoint | Scenario | Expected |
|----|----------|----------|----------|
| API-TL-01 | POST /telegram/link-code | Authenticated user | 200 + code + deep_link + expires_in=900 |
| API-TL-02 | DELETE /telegram/link | Linked user | 204 + telegram_chat_id cleared |
| API-TL-03 | DELETE /telegram/link | Unlinked user | 204 (idempotent) |

---

### 4.4 Telegram Webhook Handler Integration Tests (T080, T091)

**File**: `backend/tests/integration/test_telegram_webhook.py`  
**Setup**: All Telegram Bot API calls mocked. `TrackingService` called through real service layer. DB in test mode.

| ID | Scenario | Input | Expected |
|----|----------|-------|----------|
| TW-01 | Valid signature + `/follow` with dates (Booking URL) | Correct `X-Telegram-Bot-Api-Secret-Token` | 200 + TrackedProperty created + reply message sent |
| TW-02 | Valid signature + `/follow` URL without dates | Booking URL missing check_in | 200 + reply asking for dates + no TrackedProperty |
| TW-03 | Valid signature + `/follow` unrecognized URL | `https://tripadvisor.com/...` | 200 + error reply + no TrackedProperty |
| TW-04 | **Invalid signature** | Wrong/missing `X-Telegram-Bot-Api-Secret-Token` | **403** |
| TW-05 | Valid sig + `/follow` + already tracked | Same URL + dates sent twice | 200 + "already tracked" reply + no duplicate row |
| TW-06 | Valid sig + `/unfollow` tracked | Existing TrackedProperty | 200 + removed + confirmation reply |
| TW-07 | Valid sig + `/unfollow` not tracked | Unknown URL | 200 + "not tracked" reply |
| TW-08 | Valid sig + `/list` for linked user | User with 2 tracked searches + 1 property | 200 + formatted list reply |
| TW-09 | Valid sig + `/list` for unlinked chat | No user with that chat_id | 200 + "link first" reply + no data returned |
| TW-10 | Valid sig + `/start <code>` — fresh code | Code in Redis | 200 + user.telegram_chat_id set + code deleted |
| TW-11 | Valid sig + `/start <code>` — reused code | Code already consumed | 200 + "expired" reply + chat_id not set again |
| TW-12 | Valid sig + `/start <code>` — expired code | Code absent from Redis | 200 + "expired" reply |

---

### 4.5 Provider Contract Tests (T033, T034, maps to SC-007)

**Files**: `backend/tests/contract/test_booking_provider.py`, `test_airbnb_provider.py`  
**Constraint**: No live network. All tests use recorded HTML/JSON fixtures in `tests/contract/fixtures/`.

| ID | Provider | Scenario | Expected |
|----|----------|----------|----------|
| PC-01 | BookingProvider | `search()` against recorded listing page fixture | `SearchResult.status == OK`, listings list non-empty, each `PropertyListing` has all required fields with correct types |
| PC-02 | BookingProvider | `search()` against CAPTCHA/challenge page fixture | `SearchResult.status == CAPTCHA` or `BLOCKED`, listings empty |
| PC-03 | BookingProvider | `details()` against recorded property page fixture | `PropertyDetail` with price NUMERIC, check_in/check_out parsed correctly |
| PC-04 | BookingProvider | `parse_url()` on valid Booking URL with dates | Returns `ParsedPropertySearch` with correct `check_in`, `check_out`, `property_id` |
| PC-05 | BookingProvider | `parse_url()` on URL without dates | Returns `None` |
| PC-06 | AirbnbProvider | `search()` against recorded fixture | Same shape contract as PC-01 |
| PC-07 | AirbnbProvider | `search()` against error-page fixture | `SearchResult.status != OK` |
| PC-08 | AirbnbProvider | `parse_url()` on valid Airbnb URL with dates | Correct date extraction |
| PC-09 | AirbnbProvider | `details()` — price field type | Price is NUMERIC/Decimal, not string |
| PC-10 | TelegramNotifier | `send()` for `price_drop` event | httpx posts correct `sendMessage` payload to Bot API URL with correct `chat_id`, `text` includes old price, new price, and URL |
| PC-11 | TelegramNotifier | `send()` for `new_listing` event | httpx posts `sendMessage` with property name and URL |
| PC-12 | TelegramNotifier | Telegram API returns 400 | `send()` returns `False`, does not raise |

---

### 4.6 Safe-Discard Invariant (RELEASE GATE — FR-013)

**File**: `backend/tests/integration/test_safe_discard.py`

This test is a **hard release gate**. If it fails, the feature must not be released.

| ID | Scenario | Input | Expected |
|----|----------|-------|----------|
| SD-01 | Search worker cycle — provider returns BLOCKED | `SearchResult.status == BLOCKED` | No `TrackedSearchSeenProperty` rows written, no `NotificationLog` rows, `Notifier.send()` never called |
| SD-02 | Search worker cycle — provider returns CAPTCHA | `SearchResult.status == CAPTCHA` | Same as SD-01 |
| SD-03 | Search worker cycle — provider returns INCOMPLETE | `SearchResult.status == INCOMPLETE` | Same as SD-01 |
| SD-04 | Property worker cycle — provider returns BLOCKED | `PropertyDetail.status == BLOCKED` | No `PriceSnapshot` row, no `NotificationLog`, `Notifier.send()` not called |
| SD-05 | Search worker — one provider blocked, one OK | Booking: BLOCKED, Airbnb: OK | Airbnb results processed normally; no writes from Booking cycle |

---

### 4.7 Per-User Data Isolation (T098, maps to FR-015)

**File**: `backend/tests/integration/test_data_isolation.py`

| ID | Resource | Scenario | Expected |
|----|----------|----------|----------|
| ISO-01 | TrackedSearch | User A calls GET /tracked-searches | Only User A's rows returned |
| ISO-02 | TrackedSearch | User A calls DELETE /tracked-searches/{id_of_B} | 404 |
| ISO-03 | TrackedProperty | User A calls GET /tracked-properties | Only User A's rows |
| ISO-04 | TrackedProperty | User A calls DELETE /tracked-properties/{id_of_B} | 404 |
| ISO-05 | NotificationLog | User A calls GET /notifications | Only User A's notifications |
| ISO-06 | PriceSnapshot | Worker reads price snapshots for User A's tracked items | Cannot see User B's snapshots (scoped by TrackedSearch/Property ownership) |
| ISO-07 | Telegram chat_id | User A's `/list` command | Cannot see User B's tracked items even if chat_id collision attempted |

---

### 4.8 Auth Security Tests (T097, T098, maps to FR-001)

**File**: `backend/tests/integration/test_auth_security.py`

| ID | Scenario | Expected |
|----|----------|----------|
| SEC-01 | Login with wrong password | 401, no session created |
| SEC-02 | Unauthenticated GET /search | 401 Problem Details |
| SEC-03 | Unauthenticated POST /tracked-searches | 401 |
| SEC-04 | Unauthenticated GET /notifications | 401 |
| SEC-05 | Expired access token on protected endpoint | 401 |
| SEC-06 | Tampered JWT signature | 401 |
| SEC-07 | **Brute-force login rate limit** — 11 attempts same IP | 10th attempt may succeed if credentials valid; 11th attempt within 10-min window → 429 |
| SEC-08 | Refresh token after logout (revoked) | 401 |
| SEC-09 | Telegram link code reuse | Second `/start <code>` → "expired" (code deleted after first use) |
| SEC-10 | Telegram webhook — invalid secret | 403 (TW-04 duplicate, listed as release gate) |

---

### 4.9 Docker Compose System Gate (T100, maps to SC-006)

**Script**: `scripts/smoke-test.sh`

| ID | Check | Expected |
|----|-------|----------|
| SG-01 | `docker compose up --build` | All 7 services start (frontend, backend, worker, scheduler, db, redis, nginx) — no exit code 1 within 60s |
| SG-02 | `alembic upgrade head` against fresh DB | Exits 0, all migrations applied |
| SG-03 | GET http://localhost/api/v1/openapi.json | 200 |
| SG-04 | GET http://localhost/ | 200 (frontend served) |
| SG-05 | `alembic downgrade -1` + `alembic upgrade head` | Cycle succeeds — migration is reversible |

---

## 5. Frontend Component Tests

**Tool**: Vitest + @testing-library/react + msw

| ID | Component | Scenario | Check |
|----|-----------|----------|-------|
| FE-01 | LoginPage | Submit valid credentials | Calls POST /auth/login, redirects to /search |
| FE-02 | LoginPage | 401 response | Shows error message, no redirect |
| FE-03 | SearchPage | Submit form | Calls POST /search with correct payload |
| FE-04 | SearchProgressPage | Status=complete | Auto-redirects to /search/{id}/results |
| FE-05 | SearchProgressPage | One provider failed | Shows failure indicator for that provider |
| FE-06 | SearchResultsPage | Sort by price | Table re-orders without API call |
| FE-07 | SearchResultsPage | Export CSV | Anchor href contains /export.csv |
| FE-08 | SearchResultsPage | Zero results | Meaningful empty state visible |
| FE-09 | TrackedDashboardPage | Untrack button | Calls DELETE /tracked-searches/{id} |
| FE-10 | NotificationHistoryPage | History present | Rows with price_before → price_after |
| FE-11 | TelegramLinkPage | Not linked → Generate code | Calls POST /telegram/link-code, shows countdown |
| FE-12 | TelegramLinkPage | Linked → Unlink | Calls DELETE /telegram/link |
| FE-13 | ProtectedRoute | Unauthenticated | Redirects to /login |

---

## 6. Exploratory Testing Charter (Pre-Release)

- **Charter 1 — Search edge cases**: Search with long destination strings, special characters, past dates, check-out before check-in. Verify no 500s.
- **Charter 2 — Tracking limits under stress**: Create 10 tracked searches then attempt an 11th via both the web UI and a direct API call. Verify consistent limit enforcement.
- **Charter 3 — Telegram bot commands**: Send malformed commands (`/follow`, `/follow not-a-url`, `/follow http://` with no path), verify bot replies gracefully and no TrackedProperty rows appear.
- **Charter 4 — Session expiry**: Let access token expire, navigate to a protected page, verify silent refresh and continued session. Log out and verify refresh token cookie cleared.
- **Charter 5 — Concurrent users**: Two browser tabs, different users, same tracked item names. Verify each user sees only their own data.

---

## 7. CI/CD Integration Guidance

```yaml
# Recommended CI stages (GitHub Actions / GitLab CI)

stages:
  - lint          # mypy strict, ruff, tsc --noEmit
  - unit          # pytest backend/tests/unit/
  - contract      # pytest backend/tests/contract/
  - integration   # pytest backend/tests/integration/ (needs postgres + redis services)
  - frontend      # vitest run
  - system-gate   # docker compose up + smoke-test.sh (on main branch and release tags only)
```

**Artifact preservation**: Upload pytest XML reports and coverage HTML. Preserve for 30 days.  
**Parallelism**: Unit + contract + frontend can run in parallel. Integration requires services.

---

## 8. Test Data Strategy

- **Fixtures**: Deterministic factories using `faker` (backend) and hardcoded values (contract fixtures).
- **Provider fixtures**: Recorded HTML snapshots committed to `backend/tests/contract/fixtures/`. Never fetched live in CI.
- **User seed**: Conftest creates `user_a` and `user_b` at session scope. Tests within each module use module-scope users.
- **Reset**: Each integration test rolls back via the `db_session` fixture. No `TRUNCATE` or migration replay per test.
- **Secrets**: Tests use `pytest-dotenv` or env overrides. Never commit real `TELEGRAM_BOT_TOKEN` to fixtures.

---

## 9. Untested Areas and Accepted Risks

| Area | Why Not Tested | Risk Level | Owner |
|------|---------------|------------|-------|
| Live Booking/Airbnb scraping | No live calls in CI (by constitution) | Medium — scraper breakage discovered in staging | backend |
| Live Telegram delivery | Mocked in all CI tests | Low — contract test covers payload correctness | autotester |
| Search ≤3 min performance (SC-001) | Not automated for MVP | Medium — manual timing test pre-release | autotester |
| Frontend cross-browser | Vitest tests are jsdom only | Low — app targets modern desktop browsers | frontend |
| Nginx TLS termination | Smoke test uses HTTP internally | Low — TLS config validated on VPS deploy | devops |

---

## 10. Release Recommendation Criteria

**GO** when:
- All CI stages pass with zero failures.
- Safe-discard invariant test (§4.6) passes — **non-negotiable**.
- Per-user data isolation tests (§4.7) pass — **non-negotiable**.
- Auth security tests (§4.8) pass.
- Docker Compose system gate (§4.9) passes.
- No blocker bugs open.

**NO-GO** when:
- Safe-discard test fails.
- Any data isolation test fails.
- Unauthenticated access to protected endpoints succeeds.
- Telegram webhook signature check is bypassable.

**GO WITH RISKS** when:
- Performance (SC-001) not measured — document and plan a follow-up.
- One or more exploratory charter findings are medium severity — document and plan fixes in next iteration.
