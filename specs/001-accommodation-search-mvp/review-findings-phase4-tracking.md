# Code Review: Phase 4 — Tracking Workers (GATE 3)
**Reviewer**: code-reviewer agent
**Date**: 2026-07-19
**Scope**: T056 (TrackingService), T057 (diff logic), T058 (search worker safe-discard), T073 (property worker)
**Decision**: APPROVED — all majors resolved; re-reviewed 2026-07-19

---

## Code Review Result

### Decision
APPROVED

### Scope Reviewed
- `backend/app/services/tracking_service.py` (T056)
- `backend/app/workers/search_worker.py` (T057, T058)
- `backend/app/workers/property_worker.py` (T073)
- `backend/app/repositories/tracking_repository.py` (supporting functions)

---

## Summary

The safe-discard invariant (FR-013) is correctly implemented in both workers. TrackingService is the sole authority for tracked entity lifecycle (Constitution II ✅). No security blockers found.

Three major issues require resolution: constitution I violations in both workers (module-level provider class imports), and an incomplete `compute_search_diff` function that is dead code in production and cannot be covered by the T063 unit tests as designed.

---

## Blockers

None.

---

## Major Findings

### Major 1: Constitution I violation — module-level provider imports in `search_worker.py`

**Location**: `backend/app/workers/search_worker.py:18–19`
**Issue**:
```python
from app.providers.booking import BookingProvider
from app.providers.airbnb import AirbnbProvider
```
Both concrete provider classes are imported at module level. Constitution I states: *"no backend code outside a Provider implementation may import `BookingProvider` or `AirbnbProvider` directly."* The search route fixed this exact issue by moving the imports inside `_get_provider_registry()` as deferred local imports:
```python
def _get_provider_registry() -> dict[str, Provider]:
    from app.providers.booking import BookingProvider
    from app.providers.airbnb import AirbnbProvider
    ...
```
The same pattern is required in the worker.

**Impact**: Adding a new provider requires editing the worker file. Constitution I says only a new Provider implementation file should be required — no changes to consumers.

**Required action**: Move both imports inside `rerun_tracked_search()` or a `_build_provider_map()` helper:
```python
def _build_provider_map() -> dict[str, Any]:
    from app.providers.booking import BookingProvider
    from app.providers.airbnb import AirbnbProvider
    return {"booking": BookingProvider(), "airbnb": AirbnbProvider()}
```

---

### Major 2: Constitution I violation — module-level provider imports in `property_worker.py`

**Location**: `backend/app/workers/property_worker.py:17–18`
**Issue**: Same constitution I violation as Major 1 — `BookingProvider` and `AirbnbProvider` imported at module level.

**Required action**: Same fix pattern as Major 1. Move imports into `recheck_tracked_property()` or a helper function.

---

### Major 3: `compute_search_diff` is dead code — price-drop branch is a `pass`

**Location**: `backend/app/workers/search_worker.py:41–66`
**Issue**: The exported `compute_search_diff` function is documented as the canonical diff computation entry point, but the price-drop branch (line 63) contains only `pass` and never generates a `PriceDrop` event:
```python
else:
    # Find by property_id — need to map provider_property_id to DB property_id
    # This is done after DB upsert in the worker
    pass
```
The actual price-drop diff logic is implemented inline in `_process_tracked_search` (lines 176–207) — it works correctly in production. But `compute_search_diff` is never called by the worker; it is dead code.

**Impact**:
1. T063 unit tests are specified to test `compute_search_diff`. These tests can never cover price-drop behavior because the function never generates `PriceDrop` events. The unit tests would give false confidence.
2. The function name and docstring mislead future readers — they suggest this is the authoritative diff algorithm when it is not.

**Required action** (choose one):
- **Option A — Complete the function**: Implement price-drop detection in `compute_search_diff` by accepting `seen_map: dict[str, Decimal]` as a parameter (already built at line 53–55) and checking `if listing.provider_property_id in seen_map and current < seen_map[...]`. Then call this function from `_process_tracked_search` to make it testable.
- **Option B — Delete the function**: Remove `compute_search_diff` entirely and rename `_process_tracked_search`'s inline logic to be explicitly unit-tested by extracting the diff block into a helper. Update T063 scope to test the extracted helper.

Option A is preferred — it makes the unit-test contract honest without architectural churn.

---

## Minor Findings

### Minor 1: `guests=1` hardcoded in `property_worker.py`

**Location**: `backend/app/workers/property_worker.py:92`
**Issue**: `await prov.details(..., guests=1)` ignores the guests count that was part of the original property search. If `TrackedProperty` stores `guests`, using a hardcoded 1 produces price data for a single guest regardless of the user's actual party size.
**Impact**: Price drop comparisons may fire on price differences that are artifacts of a different guest count, not a real price change.
**Required action**: Confirm whether `TrackedProperty` model stores `guests`. If yes, pass `tp.guests` to `prov.details()`. If the field was omitted from the model, add it and populate it at creation time in `TrackingService.create_tracked_property()`.

---

### Minor 2: Redundant auto-deactivation loop in `property_worker.py`

**Location**: `backend/app/workers/property_worker.py:40–49`
**Issue**: After the main processing loop, the worker calls `get_overdue_tracked_properties` a second time to deactivate properties whose check-in has passed. However, `_process_tracked_property` already deactivates each overdue property individually (lines 61–67, with `await db.flush()`). The outer loop re-fetches the same overdue set and re-applies the same check — it is redundant for all properties that were just processed.

Additionally, the query used is `get_overdue_tracked_properties` (by schedule) rather than `get_all_active_tracked_properties`. Properties that are active but not yet overdue (scheduled for a future run) with a past check-in date will not be caught.
**Required action**: Remove the outer deactivation loop. The inner deactivation in `_process_tracked_property` is sufficient. If catch-all deactivation for non-overdue past-check-in properties is needed, use a dedicated `deactivate_expired_tracked_properties()` repository function that selects by `check_in <= today AND is_active = true`.

---

## Architecture Risk (noted — not a blocker for MVP)

**RISK-002** (per architecture review): No `SELECT FOR UPDATE` or Redis mutex on `TrackedSearchSeenProperty.min_price_seen` update. If two arq workers process the same `TrackedSearch` concurrently (unlikely but possible after crash recovery), both could read the same baseline, both detect the same price drop, and send duplicate notifications. The `upsert_seen_property` repository (lines 142–144) updates in-session but without advisory lock. Acceptable for MVP (single worker process, arq cron), but should be addressed before horizontal scaling.

---

## Constitution Check

| Rule | Status |
|------|--------|
| No code outside Provider imports BookingProvider/AirbnbProvider | ❌ MAJOR — `search_worker.py:18-19`, `property_worker.py:17-18` |
| All provider calls go through `Provider` ABC | ✅ `provider_map: dict[str, Any]` used at call sites |
| `search()` / `details()` MUST NOT raise on failure | ✅ Both providers have outer try/except returning BLOCKED |
| Safe-discard: zero DB writes if status != OK | ✅ `if not any_ok or not all_listings: return` (`search_worker:135`) |
| Safe-discard: property worker | ✅ `if detail.status != ScrapeStatus.OK or detail.listing is None: return` (`property_worker:97`) |
| TrackingService is sole authority (Constitution II) | ✅ All create/remove/dedup/interval in `tracking_service.py` only |

---

## Safe-Discard Invariant (FR-013) — Verified

**`search_worker.py`**:
- Line 123–130: Per-provider discard — `if result.status != ScrapeStatus.OK: continue`. Individual provider failures are silently discarded.
- Line 135–137: Cycle discard — `if not any_ok or not all_listings: return` **before any DB writes**. If all providers failed or returned empty, the function returns. No `notification_repository`, `tracking_repository`, or `upsert_property` calls are reached. ✅

**`property_worker.py`**:
- Line 97–103: `if detail.status != ScrapeStatus.OK or detail.listing is None: log.warning(...); return`. Function returns before `notification_repository.create_notification_log()`, `tracking_repository.update_tracked_property_after_run()`, and `db.commit()`. ✅

---

## TrackingService Single Authority (T056) — Verified

| Responsibility | Location | Status |
|----------------|----------|--------|
| create_tracked_search | `tracking_service.create_tracked_search()` only | ✅ |
| remove_tracked_search | `tracking_service.remove_tracked_search()` only | ✅ |
| create_tracked_property | `tracking_service.create_tracked_property()` only | ✅ |
| remove_tracked_property | `tracking_service.remove_tracked_property()` only | ✅ |
| Interval validation | `VALID_INTERVALS = {6, 12, 24, 48}` checked in service | ✅ |
| Dedup | `get_tracked_search_by_search_id` upsert if exists | ✅ |
| Limit enforcement | `count >= MAX_TRACKED_SEARCHES (10)` / `MAX_TRACKED_PROPERTIES (20)` | ✅ |
| Ownership check | `search.user_id != user.id → TrackingNotFoundError` | ✅ |
| `telegram_chat_id` not exposed | `_telegram_warning()` is internal only | ✅ |

---

## Required Follow-Up

| # | Owner | Severity | Action |
|---|-------|----------|--------|
| M1 | backend | Major | Move `BookingProvider`/`AirbnbProvider` imports inside helper in `search_worker.py` |
| M2 | backend | Major | Same fix in `property_worker.py` |
| M3 | backend | Major | Complete or delete `compute_search_diff`; update T063 test scope accordingly |
| m1 | backend | Minor | Verify `TrackedProperty.guests` field; pass `tp.guests` to `prov.details()` (not hardcoded 1) |
| m2 | backend | Minor | Remove redundant outer deactivation loop in `property_worker.py` |
| arch | backend | Deferred | RISK-002: Add Redis mutex or `SELECT FOR UPDATE` before horizontal worker scaling |
