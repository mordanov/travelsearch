# Specification (MVP)

## Vision
Unified accommodation search across Booking and Airbnb with common filters, normalized results, and price-drop tracking — either for a whole saved search (new/cheaper listings appearing) or for one specific property followed via the Telegram bot — for personal/family use.

## Users & Access
- Multi-user; accounts pre-created by the admin, no self-registration.
- Login via email + password.
- Each user can link their own Telegram account to receive private alerts and issue bot commands (e.g. `/follow`).

## User Scenarios & Testing

### User Story 1 — Track a saved search for new or cheaper listings
As a user, I search accommodation in a region (e.g. Oviedo) with criteria — max price/night, room count, minimum rating — and want that search to keep running in the background, so I'm notified when a new matching listing appears, or an already-seen listing drops below its lowest recorded price, without manually re-running the search.

**Acceptance Scenarios:**
1. Given a search for Oviedo (max €80/night, ≥2 bedrooms, rating ≥4.0), when I enable tracking, then the system re-runs the same search automatically at my chosen interval.
2. Given a tracked search, when a background check finds a property not present in the previous successful check, then I get a Telegram message with its name, price and link.
3. Given a tracked search, when a previously-seen property's price drops below the lowest price ever recorded for it, then I get a Telegram message showing old minimum vs. new price.
4. Given a tracked search, when nothing new or cheaper is found, then no notification is sent.

### User Story 2 — Follow a specific listing via the Telegram bot
As a user, I send a Booking or Airbnb link to the bot with `/follow <link>`, so the bot tracks that exact property for the dates encoded in the link and tells me if the price drops — without opening the web app.

**Acceptance Scenarios:**
1. Given I send `/follow <link>` and the link encodes check-in/check-out dates, when the bot parses it successfully, then it confirms tracking has started for that property and those dates.
2. Given I send `/follow <link>` and no dates can be parsed from it, when the bot fails to extract dates, then it replies asking me to resend a link that includes dates.
3. Given a followed property, when a background check finds today's price lower than the price recorded when I started following it, then I get a Telegram message with old price, new price and the link.
4. Given a followed property whose check-in date has passed, then tracking stops automatically.

### Edge Cases
- `/follow <link>` with a URL that isn't a recognized Booking/Airbnb listing → bot replies with an error, nothing is created.
- Same property + same dates already followed by this user → bot says it's already tracked, no duplicate.
- A background check is blocked/CAPTCHA'd or returns a suspiciously incomplete result → check is discarded, not diffed, retried next interval — avoids false "new listing" or false "price restored" alerts.

## Functional Requirements
1. Login (email + password).
2. Create search.
3. Select providers: Booking / Airbnb / Both.
4. Filters: destination, check-in/check-out, guests, bedrooms, bathrooms, price range, rating, free cancellation, kitchen, wifi, air conditioning, pool.
5. Run search — live scrape at request time (no caching).
6. Display progress.
7. Display merged table.
8. Sort and filter.
9. Export CSV.
10. Track a search (saved search monitoring): background re-run at a chosen interval; alert on new-matching or newly-cheaper listings (User Story 1).
11. Untrack a search.
12. Track a specific property from the results table, property page, or via the bot's `/follow <link>` command (User Story 2).
13. Untrack a property (`/unfollow` or from the web dashboard).
14. "Tracked" dashboard: both tracked searches and tracked properties, with current status.
15. Link / unlink personal Telegram account via bot deep-link + one-time code.

## Non-functional
- Async processing.
- Provider isolation.
- Extensible architecture (new provider = no backend API changes).
- Responsive UI.
- Deployed on a public VPS behind Nginx + TLS.
- Scraping resilience: proxy rotation + anti-detection to reduce blocking/CAPTCHA risk.
- Bot-triggered and UI-triggered tracking share the same backend Tracking Service — no duplicated business logic.

## Data Model
- User (id, email, password_hash, telegram_chat_id, created_at)
- Search (id, user_id, criteria, providers, status, created_at)
- SearchProvider
- Property (id, source, external_id, name, price_per_night, total_price, rating, bedrooms, bathrooms, distance, cancellation, amenities, link, ...)
- PropertyImage
- Amenity
- PriceSnapshot (property_id, price, captured_at)
- TrackedSearch (id, user_id, criteria, interval_minutes, active, last_checked_at, created_at)
- TrackedSearchSeenProperty (tracked_search_id, source, external_id, first_seen_at, min_price_seen) — diff baseline per property within a tracked search
- TrackedProperty (id, user_id, source, external_id, link, check_in, check_out, interval_minutes, baseline_price, last_price, last_checked_at, active, created_at)
- NotificationLog (id, user_id, kind [search_new_listing|search_price_drop|property_price_drop], tracked_search_id nullable, tracked_property_id nullable, sent_at, channel, price_before, price_after)

## Result Columns
Source, Name, Price/night, Total price, Rating, Bedrooms, Bathrooms, Distance, Cancellation, Amenities, Link, Track (per-property toggle)

## REST API
```
POST   /auth/login
GET    /auth/me
POST   /search
GET    /search/{id}
GET    /search/{id}/results
GET    /property/{id}
DELETE /search/{id}
POST   /search/{id}/track          { interval_minutes }
DELETE /search/{id}/track
POST   /property/{id}/track        { interval_minutes }
DELETE /property/{id}/track
GET    /user/tracked
GET    /user/notifications
GET    /user/telegram/link-code
POST   /user/telegram/unlink
POST   /telegram/webhook            (bot inbound: /follow, /unfollow, /list)
```

## Provider Interface
```python
class Provider:
    async def search(criteria): ...
    async def details(id): ...
    def parse_url(link) -> ParsedListing:   # source, external_id, check_in, check_out (if present)
        ...
```
Implemented via Playwright with proxy rotation and anti-detection (fingerprint randomization, retry/backoff on block or CAPTCHA).

Providers: booking, airbnb

## UI
- Login page
- Search form
- Progress page
- Results table (per-row "Track property" toggle + interval)
- Property details ("Track" action)
- "Track this search" action on the results page
- Tracked dashboard (searches + properties, unified view)
- Notification history (every alert ever sent — price before/after, timestamp — visible in-app; the web app is fully self-sufficient and never depends on the user having checked Telegram)
- Telegram linking screen (deep-link / one-time code)

## Background Flow
User -> API -> Job Queue -> Provider Workers (Playwright + proxy pool) -> Normalize -> PostgreSQL -> UI Polling

**Property tracking:** Scheduler (per-property interval) -> Provider.details() -> compare vs. last known price -> if lower -> Notifier -> user's Telegram

**Search tracking:** Scheduler (per-search interval) -> Provider.search(criteria) -> diff against TrackedSearchSeenProperty -> new property, or existing below its min_price_seen -> Notifier -> user's Telegram; update min_price_seen / first_seen_at

**Bot commands:** Telegram webhook -> parse command -> `/follow <link>`: Provider.parse_url() -> create/verify TrackedProperty via Tracking Service (same path as web UI) -> confirm to user

Both tracking types auto-deactivate once their relevant check-in date has passed (search-level tracking has no check-in date and runs indefinitely until untracked).

## Future Providers
Idealista, Vrbo, Holidu, HomeToGo, Expedia

## Acceptance Criteria
- Login required; no public registration endpoint exists.
- Search from one or both providers, always live.
- Unified normalized results.
- CSV export.
- A saved search can be tracked; a new or newly-cheaper matching listing triggers a Telegram alert within one interval cycle.
- A specific property can be tracked either from the web UI or via `/follow <link>` in Telegram; a price drop triggers a Telegram alert within one interval cycle.
- Tracking (search or property) stops automatically when no longer relevant (check-in passed, or user untracks).
- Docker compose starts the entire stack (frontend, backend, worker, scheduler, Postgres, Redis, Nginx with TLS).
- New provider requires no backend API changes.
