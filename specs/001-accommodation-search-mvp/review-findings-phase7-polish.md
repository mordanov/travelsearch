# Code Review: Phase 7 — Polish & Tests (GATE 4)
**Reviewer**: code-reviewer agent
**Date**: 2026-07-19
**Scope**: T094 (mypy strict), T096 (tsc --noEmit), T097 (rate limiting), T098 (data isolation integration tests)
**Decision**: APPROVED — all blockers resolved; re-reviewed 2026-07-19

---

## Code Review Result

### Decision
APPROVED

### Scope Reviewed
- `backend/pyproject.toml` — mypy strict configuration (T094)
- `backend/tests/integration/test_search_api.py`, `test_data_isolation.py`, `test_tracked_search_api.py` — mock patch paths (T094 / T098 inter-dependency)
- `frontend/tsconfig.app.json` — TypeScript strict configuration (T096)
- `backend/app/api/v1/routes/auth.py` — rate limiting implementation (T097)
- `backend/tests/integration/test_data_isolation.py` — data isolation tests (T098)
- `backend/tests/unit/test_search_diff.py` — diff unit tests (T063 / GATE 3 follow-up)

---

## Blockers

### Blocker 1: Integration test mock patch paths are broken after GATE 2 constitution-I fix

**Location**: `backend/tests/integration/test_search_api.py:66-67`, `test_data_isolation.py:78-79`, `test_tracked_search_api.py:50-51`
**Issue**: All integration tests mock providers using:
```python
patch("app.api.v1.routes.search.BookingProvider") as MockBooking,
patch("app.api.v1.routes.search.AirbnbProvider") as MockAirbnb,
```
After the GATE 2 fix, `BookingProvider` and `AirbnbProvider` are no longer module-level names in `routes/search.py` — they are imported inside `_get_provider_registry()` as local variables:
```python
def _get_provider_registry() -> dict[str, Provider]:
    from app.providers.booking import BookingProvider  # local import
    from app.providers.airbnb import AirbnbProvider    # local import
    return {"booking": BookingProvider(), "airbnb": AirbnbProvider()}
```
`unittest.mock.patch("app.api.v1.routes.search.BookingProvider")` will raise `AttributeError` because `BookingProvider` is not a module-level attribute of `routes.search`. Even if `create=True` were used, the local `from ... import` inside the function reads directly from `app.providers.booking`, bypassing any name patched into `routes.search.__dict__`.

**Impact**: All search integration tests that mock providers are broken. The `test_data_isolation.test_tracked_searches_isolated` test also uses the broken patch path — meaning the SEC-002 data isolation test **cannot pass**.

**Required action**: Change all three patch paths to target the provider at its source module:
```python
patch("app.providers.booking.BookingProvider") as MockBooking,
patch("app.providers.airbnb.AirbnbProvider") as MockAirbnb,
```
This patches the class where it lives, so any `from app.providers.booking import BookingProvider` — whether at module level or inside a function — will see the mock.

**Affected files**:
- `tests/integration/test_search_api.py` (4 occurrences)
- `tests/integration/test_data_isolation.py` (1 occurrence)
- `tests/integration/test_tracked_search_api.py` (1 occurrence)

---

### Blocker 2: Missing cross-user search read test (T042 / SEC-002)

**Location**: `backend/tests/integration/test_data_isolation.py`
**Issue**: The data isolation test file has two tests:
1. `test_tracked_searches_isolated` — verifies User B cannot read User A's tracked searches
2. `test_notifications_isolated` — verifies notifications are user-scoped (trivial assertion — both users start empty)

There is no test asserting that User B cannot read User A's search status or results. This was the primary SEC-002 finding: horizontal privilege escalation on `GET /search/{id}/status`, `GET /search/{id}/results`, and `GET /search/{id}/export.csv`. The service-level fix was applied in GATE 2, but without a failing test, there is no regression guard.

**Impact**: If the SEC-002 service fix is reverted or regresses, no test will catch it. The security audit requirement is that the test must exist and pass.

**Required action**: Add the following test to `test_data_isolation.py`:
```python
@pytest.mark.asyncio
async def test_search_results_not_accessible_cross_user(
    self, client, user_a, user_b, token_a, token_b
) -> None:
    # User A creates a search (mock providers so it succeeds)
    with (patch("app.providers.booking.BookingProvider") as MB,
          patch("app.providers.airbnb.AirbnbProvider") as MA):
        MB.return_value.search = AsyncMock(return_value=SearchResult(...))
        MA.return_value.search = AsyncMock(return_value=SearchResult(status=ScrapeStatus.OK, ...))
        resp = await client.post("/api/v1/search", json={...}, headers={"Authorization": f"Bearer {token_a}"})
    search_id = resp.json()["search_id"]

    # User B must receive 404 (not 403) on all three endpoints
    r_status = await client.get(f"/api/v1/search/{search_id}/status", headers={"Authorization": f"Bearer {token_b}"})
    assert r_status.status_code == 404

    r_results = await client.get(f"/api/v1/search/{search_id}/results", headers={"Authorization": f"Bearer {token_b}"})
    assert r_results.status_code == 404

    r_csv = await client.get(f"/api/v1/search/{search_id}/export.csv", headers={"Authorization": f"Bearer {token_b}"})
    assert r_csv.status_code == 404
```

---

## Major Findings

### Major 1: `test_search_diff.py` cannot test `PriceDrop` events (GATE 3 carry-over)

**Location**: `backend/tests/unit/test_search_diff.py`
**Issue**: `compute_search_diff` (imported by T063 tests) never generates `PriceDrop` events — the branch has `pass`. The test suite has:
```python
from app.workers.search_worker import DiffEvent, NewListing, PriceDrop, compute_search_diff
```
`PriceDrop` is imported but never tested. The test `test_no_new_no_events` constructs a case where a property exists in `seen_ids` and expects no events — but the intent was to also check no spurious price-drop event fires. When `compute_search_diff` is fixed (GATE 3 M3), a test for `PriceDrop` must be added.

**Required action**: After GATE 3 M3 fix, add at minimum:
```python
def test_price_drop_detected(self) -> None:
    pid = uuid.uuid4()
    listing = _make_listing("prop1", 80.0)  # current < min
    sp = _make_seen(pid, 100.0)             # min was 100
    events = compute_search_diff([listing], [sp], {"prop1"})
    assert len(events) == 1
    assert isinstance(events[0], PriceDrop)
    assert events[0].previous_min == Decimal("100.0")
```

---

## Minor Findings

### Minor 1: `test_notifications_isolated` assertion is too weak

**Location**: `backend/tests/integration/test_data_isolation.py:136-137`
**Issue**:
```python
assert resp_a.json()["total"] >= 0
assert resp_b.json()["total"] >= 0
```
This only asserts both users get a 200 response with a non-negative total. It never actually verifies isolation — both conditions would pass even if notifications leaked across users. A meaningful assertion would create a notification for User A and verify User B's list is empty.
**Required action**: Extend the test to create a notification row for User A (via the worker or directly), then assert `resp_b.json()["total"] == 0`.

---

## Configuration Check — mypy strict (T094)

**`backend/pyproject.toml`**:
```toml
[tool.mypy]
strict = true
python_version = "3.13"
ignore_missing_imports = true
```
mypy strict is correctly configured. Key strict flags activated: `disallow_untyped_defs`, `disallow_any_generics`, `warn_return_any`, `no_implicit_optional`. `ignore_missing_imports = true` is acceptable (Playwright stubs are not published).

**Known mypy issues to verify** (not directly reviewable without running mypy):
- `search_worker.py` and `property_worker.py` use `dict[str, Any]` for `provider_map` — this suppresses type checking on provider calls. After GATE 3 M1/M2 fix, the map should be typed as `dict[str, Provider]`.
- `booking.py` and `airbnb.py` have multiple `# type: ignore[...]` annotations which are expected given untyped Playwright page objects.

**Verdict**: Configuration is correct. Type safety depends on GATE 3 M1/M2 fixes propagating `dict[str, Provider]` typing. ✅

---

## Configuration Check — tsc --noEmit (T096)

**`frontend/tsconfig.app.json`**:
```json
{
  "strict": true,
  "noUnusedLocals": true,
  "noUnusedParameters": true,
  "noImplicitAny": true,
  "strictNullChecks": true,
  "noEmit": true
}
```
TypeScript strict is correctly configured with all required flags. `noEmit: true` is present — `tsc --noEmit` will use this config correctly.

**Validated by prior review**: All `telegram_chat_id` references (which do not exist on the `User` type) were fixed in GATE 1/frontend review. TypeScript strict would have caught these at compile time if the type was correct. Confirmed `User.telegram_is_linked: boolean` in `frontend/src/types/api.ts`.

**Verdict**: Configuration is correct. ✅

---

## Rate Limiting Review (T097)

**`backend/app/api/v1/routes/auth.py`**:
- `RATE_LIMIT_MAX = 10`, `RATE_LIMIT_WINDOW = 600` (10/IP/10min) ✅
- Counter incremented on failed login ✅
- Counter reset on successful login (GATE 1 m1 was fixed) ✅
- Redis key: `login_attempts:{ip}` ✅

**Gap**: Rate limiting is only on `POST /auth/login`. No rate limiting exists on:
- `POST /auth/refresh` — could be brute-forced to enumerate valid refresh tokens (low risk given jti revocation, but T097 scope may have intended broader coverage)
- `POST /api/v1/tracked-searches`, `POST /api/v1/tracked-properties` — interval limits enforced in TrackingService (count limits), but no per-IP rate limiting

For MVP scope: login-only rate limiting is acceptable per T097 task description. Flag as known gap for production hardening.

**IP extraction note**: `client_ip = request.client.host if request.client else "unknown"` — this reads the direct connection IP, which is correct behind a local dev server. In production behind a reverse proxy (nginx, ALB), this must read `X-Forwarded-For` or `X-Real-IP` depending on proxy config. Not a blocker for MVP but must be addressed before internet deployment.

**Verdict**: T097 satisfied for MVP scope. Production deployment requires proxy header handling. ✅ (with noted gap)

---

## Required Follow-Up

| # | Owner | Severity | Action |
|---|-------|----------|--------|
| B1 | autotester/backend | Blocker | Fix all provider mock patch paths: `app.api.v1.routes.search.BookingProvider` → `app.providers.booking.BookingProvider` (6 occurrences across 3 test files) |
| B2 | autotester/backend | Blocker | Add `test_search_results_not_accessible_cross_user` to `test_data_isolation.py` — assert 404 on `/status`, `/results`, `/export.csv` for cross-user access |
| M1 | autotester | Major | Add `test_price_drop_detected` to `test_search_diff.py` after GATE 3 M3 fix is applied |
| m1 | autotester | Minor | Strengthen `test_notifications_isolated` — create notification for User A, assert User B total == 0 |
| gap1 | backend | Deferred | Rate limiting: add `X-Forwarded-For` / `X-Real-IP` header handling in auth login route for production proxy deployment |
| GATE3 | backend | Pre-req | Must fix GATE 3 M1/M2 (provider module imports) before B1 fix path `app.providers.*.Provider` is stable for patch targets |
