# User Flows: Accommodation Search MVP

**Spec ref**: `specs/001-accommodation-search-mvp/spec.md`
**Date**: 2026-07-19

---

## Flow 1 — Login

```
[/login page]
  └─ User enters email + password → POST /auth/login
       ├─ 200 OK → store access token in memory → redirect to /search
       └─ 401 → show inline error "Invalid email or password" → stay on /login
```

**Entry**: Any unauthenticated request redirects to `/login`.
**Exit**: Successful login → `/search`.
**Error state**: Show error tied to form, not a toast. Keep credentials in fields so user can correct.

---

## Flow 2 — Search & View Results

```
[/search]
  └─ User fills form (destination, dates, guests, filters, providers)
       └─ Submit → POST /search → 202
            └─ redirect to /search/{id}/progress
                 └─ Poll GET /search/{id}/status every 3s
                      ├─ status == "running" or "partial" → show per-provider progress
                      ├─ status == "complete" → auto-redirect to /search/{id}/results
                      └─ status == "failed" (both providers failed) → show error state with "Try again"
                           └─ partial failure (one provider OK) → still redirect to results with failure banner

[/search/{id}/results]
  ├─ Sort column header → client-side re-sort (no new request)
  ├─ Column filter inputs → client-side filter
  ├─ Track toggle (row) → POST /tracked-properties (Phase 4+)
  ├─ "Track this search" button → interval modal → POST /tracked-searches (Phase 4+)
  ├─ "Export CSV" → GET /search/{id}/export.csv (anchor download)
  └─ Row click → /property/{id} (property detail)
```

**States**: empty (zero results from both providers), partial (one provider failed), full.

---

## Flow 3 — Track a Search

```
[/search/{id}/results]
  └─ Click "Track this search"
       └─ Interval modal opens (6h / 12h / 24h / 48h)
            └─ Confirm → POST /tracked-searches
                 ├─ 201 → toast "Search is now being tracked every X hours" → button changes to "Tracking ✓"
                 ├─ 422 limit → inline error in modal "You've reached the 10 tracked search limit"
                 └─ Telegram not linked → warning banner under interval picker
                      "Tracking is active but Telegram is not linked — alerts won't fire until you link."
                      [Link Telegram] action link
```

---

## Flow 4 — Track a Property (row toggle)

```
[/search/{id}/results] or [/property/{id}]
  └─ Click "Track" toggle / button
       └─ If from results row: inherits search dates automatically
          If from property detail: interval modal opens
               └─ POST /tracked-properties
                    ├─ 201 → toggle shows "Tracking" state
                    ├─ already tracked → toggle stays active (idempotent)
                    └─ 422 limit → toast error "20 property limit reached"
```

---

## Flow 5 — Tracked Dashboard

```
[/dashboard]
  ├─ Section A: Tracked Searches
  │    └─ Each row: destination, dates, interval, last-checked, next-run, status badge, [Untrack]
  │         └─ [Untrack] → confirmation popover → DELETE /tracked-searches/{id} → row removed
  └─ Section B: Tracked Properties (visible from Phase 5+)
       └─ Each row: property name (link), check-in/out, interval, min_price_seen, last-checked, [Untrack]
            └─ [Untrack] → confirmation popover → DELETE /tracked-properties/{id} → row removed
```

**Empty state** (no tracked items): show friendly callout with link to /search.

---

## Flow 6 — Notification History

```
[/notifications]
  ├─ Paginated list, newest first
  ├─ Filter by type: All / New listings / Price drops
  └─ Each item: type badge, property name (external link), price before → after, timestamp
```

**Empty state**: "No alerts yet. Track a search or property to start monitoring."
**Access**: Always reachable — does not require Telegram to be linked.

---

## Flow 7 — Telegram Linking

```
[/settings/telegram]
  ├─ Not linked state:
  │    └─ Click "Generate code"
  │         └─ POST /telegram/link-code → shows code + deep-link button + 15-min countdown
  │              └─ User opens Telegram deep-link → bot confirms link
  │                   └─ Page can detect link via polling useCurrentUser() or user refreshes
  └─ Linked state:
       └─ Shows "Linked" indicator (telegram_chat_id present)
            └─ Click "Unlink" → confirmation dialog → DELETE /telegram/link → page reverts to not-linked state
```

**Telegram bot flow** (out of scope for web UX):
```
/follow <url with dates>  →  bot confirms tracking started
/follow <url no dates>    →  bot asks to resend with dates
/unfollow <url>           →  bot confirms removed
/list                     →  bot shows active tracked searches + properties (truncated at 10)
/start <code>             →  bot confirms Telegram account linked
```

---

## Flow 8 — Error & Session Recovery

```
Any authenticated page → access token expires
  └─ Response interceptor catches 401 → POST /auth/refresh
       ├─ 200 → retry original request transparently
       └─ 401 (refresh expired/revoked) → clear in-memory token → redirect to /login
            └─ After re-login, user lands on /search (not original destination — acceptable for MVP)
```
