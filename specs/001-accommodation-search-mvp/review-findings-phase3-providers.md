# Code Review: Phase 3 — Providers & Search Service (GATE 2)
**Reviewer**: code-reviewer agent
**Date**: 2026-07-19
**Scope**: T035 (BookingProvider), T036 (AirbnbProvider), T040 (SearchService), T041 (search routes), `providers/base.py`
**Decision**: CHANGES REQUESTED — 2 blockers

---

## Code Review Result

### Decision
CHANGES REQUESTED

### Scope Reviewed
- `backend/app/providers/base.py`
- `backend/app/providers/booking.py` (T035)
- `backend/app/providers/airbnb.py` (T036)
- `backend/app/services/search_service.py` (T040)
- `backend/app/api/v1/routes/search.py` (T041)

---

## Blockers

### Blocker 1: Search routes have no user ownership check — SEC-002 unresolved

**Location**: `backend/app/api/v1/routes/search.py:54–109` and `backend/app/services/search_service.py:122–143`
**Issue**: `GET /{search_id}/status`, `GET /{search_id}/results`, and `GET /{search_id}/export.csv` all accept a `current_user` dependency but never pass `current_user.id` to the service layer. `search_service.get_status()` and `get_results_page()` query by `search_id` only — any authenticated user can read any other user's search results by guessing or enumerating UUIDs.

This is the SEC-002 horizontal privilege escalation finding from the security review. It was documented as "Add to T042 integration tests scope" and "add cross-user access assertion" but the underlying access control was never implemented.

**Impact**: Any authenticated user can read another user's search results and export their CSV. Per-user data isolation (FR-015) is violated.

**Required action**:
1. Pass `user_id` to `search_repository.get_search()` and all result queries, filtering `WHERE user_id = :user_id`.
2. In the route layer, pass `current_user.id` to `get_status` and `get_results_page`.
3. When `search.user_id != current_user.id`, return 404 (not 403) to avoid confirming resource existence.

Example fix for `get_status` in `search_service.py`:
```python
async def get_status(db, search_id, user_id) -> SearchStatusResponse | None:
    search = await search_repository.get_search(db, search_id, user_id=user_id)
    # repository filters: WHERE id = :search_id AND user_id = :user_id
```

**Evidence**: `routes/search.py:60` — `result = await search_service.get_status(db, search_id)` — `current_user.id` is not passed. `search_service.py:125` — `get_search(db, search_id)` — no `user_id` filter.

---

### Blocker 2: `RISK-001` — Playwright browser not closed on `_parse_search_results` exception

**Location**: `backend/app/providers/booking.py:62–105`, `backend/app/providers/airbnb.py` (same pattern)
**Issue**: The `async with async_playwright() as p:` block opens a browser on line 64. If `_parse_search_results()` (line 95) raises, the code falls through to the outer `except Exception` block (line 103) which logs and returns `BLOCKED` — but `browser.close()` is not called before the exception is caught. Only lines 92 and 96 call `await browser.close()`, both of which are inside the happy path and the CAPTCHA path respectively.

If `_parse_search_results` raises and the exception escapes the inner try, the `async with async_playwright()` context manager will close Playwright, but the **browser process is not explicitly closed**. Depending on Playwright version and OS, this can leak browser processes.

Software architect RISK-001 explicitly required: *"wrap ALL Playwright scrape calls in try/finally with await browser.close(). Must fire even on CAPTCHA path."*

**Impact**: Browser process leak under error conditions; resource exhaustion on repeated failures.

**Required action**: Restructure the `_do_search` method to guarantee `browser.close()` in a `finally` block:
```python
browser = await p.chromium.launch(...)
try:
    # ... scraping logic ...
finally:
    await browser.close()
```
Apply the same fix to `_do_details` in both `BookingProvider` and `AirbnbProvider`.

**Evidence**: `booking.py:64–105` — `browser.close()` called conditionally, not in `finally`. Architecture review RISK-001 required unconditional close.

---

## Major Findings

### Major 1: Provider isolation violated in `search.py` — direct class instantiation

**Location**: `backend/app/api/v1/routes/search.py:19–23`
**Issue**:
```python
def _get_provider_registry() -> dict:
    return {
        "booking": BookingProvider(),
        "airbnb": AirbnbProvider(),
    }
```
The search route directly imports and instantiates `BookingProvider` and `AirbnbProvider`. This is a constitution violation: **"no backend code outside a Provider implementation may call scraper internals directly"** and **"no API route calls BookingProvider or AirbnbProvider directly"**.

The correct pattern is dependency injection — the registry should be injected via FastAPI `Depends`, populated in `main.py` or a `providers.py` module, and typed as `dict[str, Provider]`. Routes must only see the `Provider` interface.

**Impact**: Adding a new provider now requires modifying the route file. The constitution check in `plan.md` (I.I.) says adding a provider requires only a new implementation — no changes to routes. Currently false.

**Required action**: Move provider registry construction to `app/core/providers.py` (or `app/main.py`) and inject via dependency:
```python
# app/core/providers.py
from app.providers.base import Provider
from app.providers.booking import BookingProvider
from app.providers.airbnb import AirbnbProvider

def get_provider_registry() -> dict[str, Provider]:
    return {"booking": BookingProvider(), "airbnb": AirbnbProvider()}

# In routes/search.py:
ProviderRegistry = Annotated[dict[str, Provider], Depends(get_provider_registry)]
```
This is a Major (not Blocker) because the current code still passes through the `Provider` ABC interface at the service layer — it's a boundary violation at the route level, not a functional defect.

### Major 2: `SearchStatusResponse` missing `destination`, `check_in`, `check_out` fields

**Location**: `backend/app/services/search_service.py:137–142` and `backend/app/schemas/search.py`
**Issue**: The software architect updated the API contract on 2026-07-19 to add `destination`, `check_in`, `check_out`, `guests` to `GET /search/{id}/status`. These fields are needed by `SearchResultsPage` to pass dates to `POST /tracked-properties` (fix for frontend Blocker B3). The current `SearchStatusResponse` does not include these fields.
**Impact**: Frontend B3 cannot be fixed properly until this is in the response schema. Track-property feature remains broken.
**Required action**: Add `destination: str`, `check_in: date`, `check_out: date`, `guests: int` to `SearchStatusResponse` Pydantic schema and populate from the `Search` row in `get_status()`.

---

## Minor Findings

### Minor 1: `_get_provider_registry` returns an untyped `dict`

**Location**: `backend/app/api/v1/routes/search.py:19`
**Issue**: Return type annotation is `dict` not `dict[str, Provider]`. This also means mypy strict may infer `dict[str, BookingProvider | AirbnbProvider]` rather than `dict[str, Provider]`.
**Required action**: Add proper return type. Addressed by the Major 1 fix.

### Minor 2: `SEARCH_STATUS_KEY` defined but unused

**Location**: `backend/app/services/search_service.py:23`
**Issue**: `SEARCH_STATUS_KEY = "search:status:{search_id}"` is defined but never used. Search status is stored directly in the DB, not in Redis. The constant is dead code.
**Required action**: Remove the constant to avoid confusion about architecture (there's no Redis status cache).

### Minor 3: `export_csv` fetches up to 10,000 rows into memory at once

**Location**: `backend/app/services/search_service.py:196–233`
**Issue**: `get_results_page(size=10000)` loads all results into a string in memory, then wraps in a single `yield`. For large result sets this defeats the purpose of `StreamingResponse`.
**Impact**: For MVP scale (personal use, <200 results per search) this is fine. For larger deployments this would be a problem. Flag as a known limitation.
**Required action**: Document as accepted limitation. Not a blocker for MVP.

---

## Constitution Check — Provider Isolation

| Rule | Status |
|------|--------|
| No backend code outside Provider calls scraper internals | ⚠️ PARTIAL — route imports BookingProvider/AirbnbProvider directly (Major 1) |
| All provider calls go through typed Provider interface | ✅ service layer uses `Provider` ABC correctly |
| search() / details() MUST NOT raise on failure | ✅ Both providers have outer try/except returning BLOCKED |
| parse_url() is pure (no network calls) | ✅ URL parsing only, no requests |
| browser.close() guaranteed in finally | ❌ BLOCKED — not in finally (Blocker 2) |

---

## Safe Scraping Invariant (FR-013)

**In `search_service.run_search()`**: `if result.status != ScrapeStatus.OK: return early` (line 76–78) — partial/failed provider results are NOT written to DB. ✅ Safe-discard for search service is correct.

---

## Tests and Evidence Reviewed

Tests for provider contract (`test_booking_provider.py`, `test_airbnb_provider.py`) not yet reviewed — will review when autotester delivers output. The safe-discard invariant in T057 (search diff worker) and T073 (property worker) are covered by GATE 3.

---

## Required Follow-Up

| # | Owner | Severity | Action |
|---|-------|----------|--------|
| B1 | backend | Blocker | Add `user_id` filter to `get_status`, `get_results_page`, `export_csv` — pass `current_user.id` from routes |
| B2 | backend | Blocker | Wrap Playwright `browser` in `try/finally: await browser.close()` in `_do_search` and `_do_details` for both providers |
| M1 | backend | Major | Move provider registry to DI module — routes must not import BookingProvider/AirbnbProvider |
| M2 | backend | Major | Add `destination`, `check_in`, `check_out`, `guests` to `SearchStatusResponse` (per updated API contract) |
| m1 | backend | Nit | Remove unused `SEARCH_STATUS_KEY` constant |
| verify | code-reviewer | Required | Re-review B1+B2 fixes; confirm T042 integration tests cover cross-user access (SEC-002) |
