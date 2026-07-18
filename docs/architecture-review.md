# Architecture Review: Accommodation Search MVP

**Date**: 2026-07-19 | **Branch**: `001-accommodation-search-mvp`
**Reviewer**: software-architect agent

---

## 1. Plan and Data Model Review

### 1.1 Correctness Assessment

All reviewed artifacts (`plan.md`, `data-model.md`, `spec.md`, `contracts/api.md`,
`contracts/provider-interface.md`, `research.md`, `constitution.md`) are internally
consistent. The constitution gates in `plan.md` all pass.

**No contradictions found** between the data model entities and the API contract shapes.
`hashed_password` correctly appears only in the `User` model and is explicitly excluded
from all Pydantic response schemas.

### 1.2 Completeness Gaps (non-blocking)

**GAP-001** — `GET /auth/me` in constitution but absent from `contracts/api.md`

The constitution lists `GET /auth/me` but the final API contract omits it. The frontend
`useCurrentUser()` hook (T092) needs to know whether the user has Telegram linked.
The current plan routes this through `useAuth`, which only exposes `isAuthenticated`.

**Recommendation**: Add `GET /auth/me` to the API contract returning:
```json
{"id": "<uuid>", "email": "...", "telegram_is_linked": true}
```
Per SEC-008, the raw `telegram_chat_id` MUST NOT appear in any API response — use
a boolean `telegram_is_linked` flag instead.

**Status**: RESOLVED — `contracts/api.md` updated with the correct `GET /auth/me` shape.

**GAP-002** — `SearchResult` storage model is ambiguous

`data-model.md` says results are "held in Redis during execution and discarded after
the session window" but also defines a `SearchResult` entity with FK → `Property`.
The plan (T031) creates a `SearchResult` SQLAlchemy model and T038 creates
`search_repository.py` with `add_results()` and `get_results_page()`.

This is actually consistent — `SearchResult` rows ARE persisted to PostgreSQL (for
the results page and CSV export), while `search:{id}:status` in Redis is only the
live progress indicator. The data-model description is misleading. **No code change
needed**, but the data-model.md `Search` entity description should clarify this.

**GAP-003** — `PropertyImage` and `Amenity` entities in constitution but absent from data-model

The constitution mentions `PropertyImage` and `Amenity` as separate entities. The
final data-model uses `amenities JSONB` on `Property` instead. This is the correct
simplification for MVP (JSONB is flexible and avoids a join table). No gap in
implementation — just a documentation delta from the constitution.

**GAP-004** — `TrackedProperty.interval_hours` default not specified

`TrackedProperty` has `interval_hours CHECK IN (6,12,24,48)` but no DEFAULT. The
API contract for `POST /tracked-properties` requires `interval_hours` in the request
body, so a default is unnecessary — but the Alembic migration (T071) should omit
DEFAULT to match this intent explicitly.

**GAP-005** — `PriceSnapshot` written for TrackedSearch too

`data-model.md` says `PriceSnapshot.source` is `'property_worker' | 'search_worker'`.
But `research.md` section 2 and T058 describe the search worker updating
`TrackedSearchSeenProperty.min_price_seen` — it's unclear whether `PriceSnapshot`
is also written by the search worker or only by the property worker.

**Recommendation**: Clarify in `data-model.md` that `PriceSnapshot` is written by
BOTH workers. The `source` field distinguishes them. This has no implementation impact
(T058 and T073 already reference `PriceSnapshot` writes) but removes ambiguity for
developers.

---

## 2. Phase Dependency Order Assessment

The 7-phase order in `tasks.md` is sound:

| Phase | Dependency | Assessment |
|-------|-----------|-----------|
| Phase 1 (Setup) | None | Correct — scaffolding only |
| Phase 2 (Foundational) | Phase 1 | Correct — all stories need auth + DB + interfaces |
| Phase 3 (US1 Search) | Phase 2 | Correct — needs auth, Provider ABC, DB models |
| Phase 4 (US2 Tracking) | Phase 2 + Phase 3 | Correct — TrackedSearch references search_id |
| Phase 5 (US3 Bot Follow) | Phase 2 + Phase 4 | Correct — needs TrackingService + TelegramNotifier |
| Phase 6 (US4 Linking) | Phase 2 + Phase 5 | Correct — webhook endpoint already exists in Phase 5 |
| Phase 7 (Polish) | All phases | Correct |

**One dependency clarification**: T023–T026 (frontend auth shell) are in Phase 2 and
marked as parallel with backend tasks. This is correct — frontend auth shell has no
dependency on backend being ready (it's built against the API contract). The Axios
interceptor (T023) will work once the backend auth endpoint exists.

**Within Phase 3, sequential dependency chain is correct**:
T032 (migration) → T035/T036 (providers) → T040 (SearchService) → T041 (routes) →
T042 (integration tests) → T046 (SearchResultsPage needs API shape).

---

## 3. Architecture Risks

### RISK-001 — Playwright browser lifecycle management [HIGH]

**Risk**: If a Playwright browser is not properly closed after a scrape failure, the
container accumulates zombie Chromium processes. At 6h intervals with two providers,
this is 8 browser launches per day per tracked search — manageable, but leaks compound.

**Mitigation required**: The `BookingProvider` and `AirbnbProvider` implementations
(T035, T036) MUST wrap the entire scrape in:
```python
async with async_playwright() as p:
    browser = await p.chromium.launch(...)
    try:
        ...
    finally:
        await browser.close()
```
The `finally` block must fire even on CAPTCHA detection or network timeout.

**Fitness function**: `tests/contract/test_booking_provider.py` should assert that a
provider call with a fixture that triggers a CAPTCHA path does NOT leave a running
Playwright process (use `psutil` to count Chromium processes before and after).

### RISK-002 — arq job concurrency and per-property DB contention [MEDIUM]

**Risk**: If the scheduler enqueues multiple `rerun_tracked_search` jobs and they run
concurrently, two jobs for the same `TrackedSearch` could both pass the `next_run_at`
check, both run the provider, and both write to `TrackedSearchSeenProperty` — creating
a race condition in the baseline update.

**Mitigation**: The `rerun_tracked_search` job should acquire a distributed lock on the
`TrackedSearch.id` (Redis `SET nx ex`) before processing. If the lock is already held,
skip this cycle (the other job will complete normally). This is an implementation
requirement for T058.

**Alternative**: Set `next_run_at = now() + interval` as the FIRST DB write in the job
(before scraping), inside a `SELECT FOR UPDATE`. This prevents double-processing without
a Redis lock.

### RISK-003 — Search results ephemeral window [LOW]

**Risk**: `SearchResult` rows in PostgreSQL are created during the search. But if the
frontend loads `GET /search/{id}/results` for a search that completed days ago, do the
results still exist? The data-model description implies they might be "discarded" but
the schema has no TTL/expiry column.

**Clarification needed**: Search results should be durable until the user explicitly
deletes the search or a retention policy removes old searches. No automatic expiry is
defined. This is fine for MVP but should be documented explicitly.

### RISK-004 — Telegram webhook secret not rotatable without downtime [LOW]

**Risk**: `TELEGRAM_WEBHOOK_SECRET` is configured once in `.env` and registered with
Telegram via `setWebhook`. Rotating it requires re-registering the webhook, which
means a brief window where Telegram sends updates with the old secret to a handler
expecting the new one.

**Mitigation**: Document in `docs/operations.md` (to be authored by devops): rotation
procedure is (1) update `.env` with new secret, (2) immediately re-register webhook,
(3) restart the backend container. Window of dropped updates is < 1 minute.

### RISK-005 — No per-property lock in property worker [MEDIUM]

Same class as RISK-002 but for `recheck_tracked_property`. If two worker instances
run (e.g., two `worker` containers in a future multi-replica scenario), the same
`TrackedProperty` could be processed twice. Same mitigation: Redis lock on
`TrackedProperty.id` before processing, or `next_run_at` update as the first DB write.

---

## 4. Well-Architected Review Summary

| Pillar | Status | Notes |
|--------|--------|-------|
| Operational Excellence | PASS | Structured logging, health checks, Docker Compose gates all defined |
| Security | PASS with conditions | Argon2id + JWT hardened pattern; brute-force (T097) and data isolation (T098) are explicit tasks; Telegram webhook validation (T076) required |
| Reliability | PASS with conditions | Safe-discard invariant enforced in T057/T073; RISK-002/RISK-005 (worker concurrency) must be addressed in implementation |
| Performance Efficiency | PASS | SC-001 (3 min total) is achievable with concurrent `asyncio.gather()` for dual-provider search; no bottleneck identified |
| Cost Optimization | PASS | Single VPS, Docker Compose, no cloud services; Redis and PostgreSQL are the only stateful dependencies |
| Sustainability/Maintainability | PASS | Provider isolation (ADR 002) makes the system extensible; constitution compliance gates maintain quality |

---

## 5. ADR Index

Four ADRs authored for this feature:

| ADR | Title | Status |
|-----|-------|--------|
| [ADR 001](../docs/adr/001-async-stack-fastapi-arq.md) | Async Stack — FastAPI + arq | Accepted |
| [ADR 002](../docs/adr/002-provider-notifier-isolation.md) | Provider and Notifier Isolation Pattern | Accepted |
| [ADR 003](../docs/adr/003-redis-ephemeral-state.md) | Redis for Ephemeral and Transient State | Accepted |
| [ADR 004](../docs/adr/004-auth-jwt-argon2id.md) | Authentication — JWT + Argon2id | Accepted |

---

## 6. Recommendations for Implementation Agents

### For backend (immediate):

1. In `Provider` implementations (T035, T036): wrap all Playwright calls in
   `try/finally` with `await browser.close()` — see RISK-001. ✅ RESOLVED (Gate 2)
2. In `rerun_tracked_search` (T058) and `recheck_tracked_property` (T073): update
   `next_run_at` as the first DB write (or use Redis lock) to prevent duplicate
   processing — see RISK-002, RISK-005.
3. Add `GET /auth/me` endpoint alongside the auth routes (T017) — see GAP-001. ✅ RESOLVED
4. Full provider registry DI pattern (`app/core/providers.py` + `app.state.providers`
   + `Depends(get_providers)` in routes/workers) — required before Phase 7 for complete
   SC-007 compliance. Currently partially applied (local imports, not DI injection).

### For autotester:

1. All mock patch paths must target `app.providers.booking.BookingProvider` and
   `app.providers.airbnb.AirbnbProvider` (the definition site), NOT the import site
   in routes/workers. Or use `app.dependency_overrides[get_providers]` for cleaner
   isolation once full DI is in place.
2. SEC-002 cross-user search isolation tests: GET /search/{id}/status, /results,
   /export.csv with wrong user JWT → all must return 404.
3. Price-drop path in tracked search worker must have an explicit test: seed
   min_price_seen=100, mock provider returning 85, assert NotificationLog created.

### For security-architect:

1. Review T097 (brute-force protection) — ensure Redis counter resets on successful
   login (resolved Gate 4) and X-Forwarded-For handling is documented as deferred.
2. Review T076 (Telegram webhook validation) — ✅ RESOLVED: empty-body 403 +
   `secrets.compare_digest` timing-safe comparison confirmed in Gate 1.

## 7. Resolution Status

| ID | Finding | Status |
|----|---------|--------|
| RISK-001 | Playwright browser leak | ✅ Fixed (Gate 2) |
| RISK-002 | arq race on TrackedSearch | Mitigated — next_run_at updated as first DB write pattern |
| RISK-005 | arq race on TrackedProperty | Mitigated — same pattern |
| RISK-003 | SearchResult durability | ✅ Clarified (durable, no TTL, comment in repo) |
| RISK-004 | Telegram secret rotation | ✅ Documented in quickstart.md (devops) |
| GAP-001 | GET /auth/me missing | ✅ Fixed (Gate 1, contract + code updated) |
| GAP-002 | SearchResult storage description | ✅ Clarified (docs only) |
| GAP-005 | PriceSnapshot from search worker | ✅ Confirmed in T058 implementation |
| M3 Gate3 | compute_search_diff dead code | ✅ Fixed — pure function restored, 7 unit tests including price-drop |
| M1/M2 Gate3 | Worker Constitution I violation | ✅ Fixed — arq ctx-based DI pattern |
| B1 Gate4 | Mock patch paths broken | ✅ Fixed — all 6 paths updated to definition site |
| B2 Gate4 | SEC-002 search cross-user test | ✅ Fixed — test_search_results_not_accessible_cross_user added |

**All 4 review gates: APPROVED. Implementation is code-review-complete.**
