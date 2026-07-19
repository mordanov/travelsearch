# Research: Accommodation Search MVP

**Branch**: `001-accommodation-search-mvp` | **Date**: 2026-07-19

## 1. Playwright Async Scraping Patterns

**Decision**: Use `AsyncPlaywright` context manager per scrape job; one browser context per
worker invocation; never share a browser instance across concurrent arq jobs.

**Rationale**: Browser context isolation prevents cookies/fingerprints leaking between jobs.
Per-job contexts also allow safe per-job proxy assignment. Sharing a browser instance across
concurrent jobs risks one job's block state affecting another.

**Pattern**:
```python
async with async_playwright() as p:
    browser = await p.chromium.launch(proxy={"server": proxy_url})
    context = await browser.new_context(...)
    page = await context.new_page()
    # ... scrape ...
    await browser.close()
```

**Alternatives considered**: Persistent browser pool (rejected — fingerprint accumulation
risk, harder to rotate proxies per-job).

---

## 2. arq Worker Design for Background Jobs

**Decision**: Two separate arq worker functions — `rerun_tracked_search` and
`recheck_tracked_property` — scheduled via arq's `cron` scheduler. Each job is idempotent
and self-contained: it fetches its own DB session, calls the provider interface, applies
safe-discard logic, and writes results. Jobs do not share state.

**Rationale**: Separate functions per job type keep the safe-discard invariant local and
testable in isolation. arq's built-in cron is sufficient for 6h/12h/24h/48h granularity;
no external cron daemon needed.

**Scheduling approach**: `TrackedSearch` and `TrackedProperty` rows each store a
`next_run_at` timestamp. The arq scheduler wakes periodically (e.g., every 5 minutes) and
enqueues jobs whose `next_run_at` has passed. This avoids a separate cron table and keeps
scheduling data co-located with the entity.

**Alternatives considered**: APScheduler (rejected — extra dependency, doesn't integrate
cleanly with arq); storing interval in Redis (rejected — DB is the source of truth).

---

## 3. Safe-Discard Implementation Pattern

**Decision**: Each `Provider.search()` and `Provider.details()` call returns a structured
result that includes a `status` field: `ok | blocked | captcha | incomplete`. The worker
checks `status` before any diff or write. If status is not `ok`, the cycle is logged and
discarded — no database writes, no notifications.

**"Incomplete" detection**: Provider-specific threshold. For Booking and Airbnb, if a
search returns fewer than `PROVIDER_MIN_RESULTS` (configurable per provider, defaults to 1)
AND the previous successful cycle returned more, the cycle is flagged `incomplete`.

**Rationale**: Making status explicit in the return type forces callers to handle it;
there is no way to accidentally use a blocked result. The threshold approach handles the
most common real-world case (CAPTCHA returns 0 results or a challenge page).

---

## 4. Telegram Bot Integration

**Decision**: Webhook mode (not polling). The bot receives updates at
`POST /api/v1/telegram/webhook`. The endpoint validates the `X-Telegram-Bot-Api-Secret-Token`
header before processing. All bot command handling delegates to `TrackingService` for
tracking operations and to `NotificationService` for message dispatch.

**Commands**: `/start`, `/follow <url>`, `/unfollow <url>`, `/list`, `/help`.

**Linking flow**:
1. User visits `/settings/telegram` in the web app.
2. Backend generates a short-lived (15-minute) one-time code, stores it in Redis with the
   user's ID.
3. Web app shows the code and a deep-link: `https://t.me/<botname>?start=<code>`.
4. User clicks deep-link; Telegram sends `/start <code>` to the bot.
5. Bot looks up the code in Redis, links `telegram_chat_id` to the user record, deletes the
   code, and replies confirming the link.

**Alternatives considered**: Polling (rejected — requires long-running thread or separate
process; webhook is simpler on a VPS with public HTTPS); OAuth via Telegram Login Widget
(overkill for MVP, requires additional web handling).

---

## 5. JWT Session Strategy

**Decision**: Short-lived access token (15 minutes) + long-lived refresh token (30 days),
both signed with HS256 using `JWT_SECRET`. Access token stored in-memory on the frontend
(React state / React Query context). Refresh token stored as `HttpOnly; Secure; SameSite=Strict`
cookie. A single Axios request interceptor handles 401 → refresh → retry transparently.

**Rationale**: In-memory access token prevents XSS token theft. HttpOnly cookie for refresh
prevents JS access to the long-lived credential. This is the standard hardened JWT pattern
for SPAs.

**Alternatives considered**: localStorage for both tokens (rejected — XSS risk);
sessionStorage (rejected — lost on tab close, poor UX); server-side sessions (rejected —
more complex to scale, conflicts with JWT preference).

---

## 6. Provider Interface URL Parsing for `/follow`

**Decision**: `Provider.parse_url(url: str) -> ParsedPropertySearch | None` returns a
structured object containing `property_id`, `check_in: date`, `check_out: date`, and
`guests: int` if the URL is a recognized listing with dates encoded. Returns `None` if the
URL is not a recognized listing or lacks date parameters.

**Booking URL pattern**: `booking.com/hotel/<name>.html?checkin=YYYY-MM-DD&checkout=YYYY-MM-DD&...`
**Airbnb URL pattern**: `airbnb.com/rooms/<id>?check_in=YYYY-MM-DD&check_out=YYYY-MM-DD&...`

**Date-absent URLs**: Bot replies asking the user to resend a link with dates (US3, Acceptance
Scenario 2). The bot does NOT prompt interactively for dates — the user must resend.

---

## 7. Per-User Tracking Limits Enforcement

**Decision**: `TrackingService.create_tracked_search()` and `create_tracked_property()` each
perform a count query before insertion. If the count equals or exceeds the limit (10 for
searches, 20 for properties), a `TrackingLimitExceededError` is raised. The API layer
converts this to HTTP 422 with a clear message. The Telegram bot handler converts it to a
bot reply message.

**Rationale**: Enforcing in the service layer (not in the route or bot handler) satisfies
FR-009 (single authority) and FR-016 simultaneously.

---

## 8. Search Progress Streaming to Frontend

**Decision**: The frontend polls `GET /api/v1/search/{search_id}/status` at a 3-second
interval while the search is running. The status response includes `status` (pending |
running | partial | complete | failed), `results_count`, and per-provider status. When
status is `complete`, the frontend redirects to the results page.

**Rationale**: SSE or WebSocket adds complexity for a use case that only fires once per
search session. Polling at 3-second intervals is well within the 3-minute timeout budget
and is simpler to implement, test, and debug.

**Alternatives considered**: Server-Sent Events (rejected — requires persistent connection,
complicates Nginx proxying); WebSocket (rejected — overkill for one-shot polling).

---

## 9. CSV Export

**Decision**: `GET /api/v1/search/{search_id}/export.csv` returns a streaming CSV response
from the server. All columns from the results table are included. The frontend "Export CSV"
button is a simple anchor `href` to this endpoint (no client-side CSV generation).

**Rationale**: Server-side generation keeps CSV logic in one place; no need to ship a CSV
library to the browser; streaming handles large result sets without buffering.

---

## 10. Notification History In-App

**Decision**: `NotificationLog` records every alert dispatched, regardless of channel.
`GET /api/v1/notifications` returns the full history for the authenticated user, paginated
(50 per page). The frontend `NotificationHistoryPage` renders this independently of Telegram
state — it is always accessible whether or not Telegram is linked (FR-011).
