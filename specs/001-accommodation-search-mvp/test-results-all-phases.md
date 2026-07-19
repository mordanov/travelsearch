# Test Results — All Phases

**Feature**: `001-accommodation-search-mvp`  
**Run date**: 2026-07-19  
**Author**: autotester  
**Environment**: macOS Darwin 25.5.0, Python 3.13, /tmp/ts-test-venv

---

## Summary

| Layer | Tests | Passed | Failed | Skipped | Notes |
|-------|-------|--------|--------|---------|-------|
| Unit | 18 | **18** | 0 | 0 | All green |
| Contract | 14 | **14** | 0 | 0 | All green |
| Integration | 20 | — | — | 20 | Requires live PostgreSQL + Redis — not available locally |
| **Total runnable** | **32** | **32** | **0** | — | **100% pass rate** |

---

## Unit Tests (18/18 PASSED)

**File**: `tests/unit/test_property_worker.py` — 4 tests  
- `test_price_drop_creates_notification` ✅  
- `test_price_above_min_no_notification` ✅  
- `test_blocked_status_discards` ✅ ← safe-discard invariant  
- `test_check_in_passed_deactivates` ✅

**File**: `tests/unit/test_search_diff.py` — 7 tests  
- `test_empty_listings_safe_discard` ✅ ← safe-discard invariant  
- `test_new_listing_not_in_baseline` ✅  
- `test_all_new_listings` ✅  
- `test_no_event_when_price_unchanged` ✅  
- `test_no_event_when_price_rises` ✅  
- `test_price_drop_detected` ✅ ← Gate 4 M1 (was missing, confirmed present and passing)  
- `test_mixed_new_and_price_drop` ✅

**File**: `tests/unit/test_tracking_service.py` — 7 tests  
- `test_creates_new_tracked_search` ✅  
- `test_returns_existing_on_duplicate` ✅  
- `test_raises_on_limit_exceeded` ✅  
- `test_raises_on_invalid_interval` ✅  
- `test_raises_on_search_not_found` ✅  
- `test_deactivates_on_remove` ✅  
- `test_raises_not_found` ✅

---

## Contract Tests (14/14 PASSED)

**File**: `tests/contract/test_booking_provider.py` — 5 tests  
- `test_parse_url_valid_booking_url` ✅  
- `test_parse_url_missing_dates_returns_none` ✅  
- `test_parse_url_non_booking_url_returns_none` ✅  
- `test_normalize_maps_raw_dict` ✅  
- `test_search_blocked_returns_blocked_status` ✅

**File**: `tests/contract/test_airbnb_provider.py` — 5 tests  
- `test_parse_url_valid_airbnb_url` ✅  
- `test_parse_url_missing_dates_returns_none` ✅  
- `test_parse_url_non_airbnb_url_returns_none` ✅  
- `test_normalize_maps_raw_dict` ✅  
- `test_search_returns_blocked_on_challenge` ✅

**File**: `tests/contract/test_telegram_notifier.py` — 4 tests  
- `test_sends_price_drop_message` ✅  
- `test_sends_new_listing_message` ✅  
- `test_returns_false_on_api_error` ✅  
- `test_returns_false_not_raises_on_network_error` ✅

---

## Integration Tests (require PostgreSQL + Redis)

Not executed: no local PostgreSQL with role `postgres` available. These tests run in CI with `services: postgres, redis` as defined in `.github/workflows/ci.yml`. Files exist and were code-reviewed (Gates 2–4 approved):

- `test_search_api.py` — 4 tests (202, status poll, pagination, CSV export)
- `test_data_isolation.py` — 3 tests (tracked search isolation, **SEC-002 search isolation**, notifications isolation)
- `test_tracked_search_api.py`
- `test_telegram_webhook.py` — includes invalid-signature → 403
- `test_telegram_linking.py`

---

## Test Infrastructure Fixes Applied This Run

Three test infrastructure bugs found and fixed (not in production code):

| Fix | File | Description |
|-----|------|-------------|
| Patch path | `tests/unit/test_property_worker.py` | `app.workers.property_worker.get_by_id` → `app.repositories.user_repository.get_by_id` (local import inside function, must patch at definition point) |
| Patch path | `tests/contract/test_booking_provider.py` | `app.providers.booking.async_playwright` → `playwright.async_api.async_playwright` (same reason) |
| Patch path | `tests/contract/test_airbnb_provider.py` | `app.providers.airbnb.async_playwright` → `playwright.async_api.async_playwright` |
| No-op DB fixture | `tests/unit/conftest.py` (new) | Added session-scoped `create_tables` no-op to prevent unit tests from requiring a PostgreSQL connection |
| No-op DB fixture | `tests/contract/conftest.py` (new) | Same for contract tests |

---

## Warnings (non-blocking)

11 `DeprecationWarning: datetime.datetime.utcnow()` instances in application code and test fixtures. Python 3.13 deprecates `utcnow()` in favour of `datetime.now(datetime.UTC)`. Should be addressed in Phase 7 hardening — no functional impact.

---

## Release Recommendation

**GO WITH RISKS**

- All 32 runnable tests pass (18 unit + 14 contract).
- Safe-discard invariant confirmed passing (both `test_blocked_status_discards` and `test_empty_listings_safe_discard`).
- `test_price_drop_detected` confirmed passing — US2 price-drop notification path is exercised.
- Integration tests cannot be run locally (no PostgreSQL); CI is the authoritative gate. All code-review gates (1–4) are approved.
- Known follow-up items: `datetime.utcnow()` deprecation warnings, refresh token rotation integration test, brute-force rate-limit 429 integration test.
