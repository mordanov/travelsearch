# Constitution

## Purpose
Build a modular accommodation search & price-tracking platform aggregating multiple providers (initially Booking and Airbnb), for personal/family use, deployed on a public VPS with multi-user access and a bidirectional Telegram bot.

## Core Principles
- Python 3.13, FastAPI (async), React 19 + TypeScript, PostgreSQL.
- Docker Compose for deployment on VPS.
- Nginx as reverse proxy with TLS (Let's Encrypt).
- REST APIs only.
- Strict typing (mypy, TypeScript strict).
- Ruff, pytest.
- Configuration only via .env (DB creds, proxy provider credentials, Telegram bot token, JWT secret).
- SQLAlchemy 2.x + Alembic.
- Pydantic v2.
- Playwright for scraping-based providers (async, fits FastAPI's async stack).
- Redis + arq for background job queue and scheduled price checks (async-native, no separate broker like RabbitMQ needed).

## Architecture
- frontend/
- backend/
- scraper/
- providers/
- notifications/ (Telegram bot: inbound commands + outbound alerts, isolated like providers)
- database/
- nginx/
- docker/

Backend never communicates directly with provider implementations. All providers implement a common Provider interface.
Backend never communicates directly with notification channels. All notification channels implement a common Notifier interface (Telegram first, extensible later — e.g. email, push).

## Provider Contract
```python
class Provider:
    async def search(criteria): ...
    async def details(id): ...
    def parse_url(link) -> ParsedListing: ...   # source, external_id, check_in, check_out (if present in URL)
    def normalize(raw) -> Property: ...
```
Each provider is isolated, replaceable, and responsible for its own anti-bot handling (proxy rotation, retry/backoff, fingerprint randomization, CAPTCHA detection) behind this uniform interface. Proxy pool is configured via .env, provider-agnostic.

## Flight Provider Contract
```python
class FlightProvider:
    async def explore(origin_airport, date_range, min_nights, max_nights) -> list[FlightCandidate]: ...
    # "anywhere + flexible dates" search — uses the provider's own explore/everywhere mode
    # (Google Flights Explore, Skyscanner Everywhere) instead of brute-forcing city×date combos
    async def search(origin_airport, destination_airport, depart_date, return_date) -> list[Flight]: ...
```
Flight providers are scraping-based, like accommodation providers, and follow the same isolation/anti-bot principles. They typically face stricter bot detection than hotel sites, so the same proxy/antidetect infra applies with a lower expected success rate per cycle — see Risk Notes.

## Notifier Contract
```python
class Notifier:
    async def send(user, message): ...
```
Telegram is bidirectional: it both sends alerts (Notifier) and receives commands (`/follow`, `/unfollow`, `/list`) via a webhook. Inbound commands are handled by a dedicated command handler in `notifications/`, which delegates to the same Tracking Service used by the REST API — command handling never re-implements business logic.

## Tracking Service (shared)
A single backend service owns all tracking logic (create/remove TrackedSearch, create/remove TrackedProperty, dedup checks, interval validation). Both the REST API (web UI) and the Telegram command handler (`/follow`) call into this service, so behavior is identical regardless of entry point.

## Authentication & Users
- Multi-user; no public self-registration. Accounts are provisioned manually by the admin (CLI script or admin-only endpoint).
- Email + password login; passwords hashed with Argon2id; session via JWT.
- Each user may link a personal Telegram chat, via bot deep-link + one-time linking code, both to receive alerts and to issue commands like `/follow` tied to their own account.
- Basic rate limiting / brute-force protection on `/auth/login`.

## Background Jobs
Two independent scheduler types, both driven by per-item configurable intervals:
- **Property-level:** re-fetch `Provider.details()` for each active TrackedProperty; notify on price drop vs. last known price; auto-deactivate after check-in date passes.
- **Search-level:** re-run `Provider.search()` for each active TrackedSearch; diff results against `TrackedSearchSeenProperty`; notify on a brand-new matching property or an existing one dropping below its recorded minimum; update the seen-property baseline.

**Safety rule:** a scrape cycle that is blocked, CAPTCHA'd, or returns a suspiciously incomplete result set must be discarded rather than diffed or compared — never trust a partial result enough to trigger a false "new listing" or false "price restored" notification.

## Database
Persist users, searches, properties, price history (PriceSnapshot), amenities, images, tracked searches (+ seen-property baselines), tracked properties, and notification logs.

## API
```
POST   /auth/login
GET    /auth/me
POST   /search
GET    /search/{id}
GET    /search/{id}/results
GET    /property/{id}
DELETE /search/{id}
POST   /search/{id}/track           { interval_minutes }
DELETE /search/{id}/track
POST   /property/{id}/track         { interval_minutes }
DELETE /property/{id}/track
GET    /user/tracked
GET    /user/notifications
GET    /user/telegram/link-code
POST   /user/telegram/unlink
POST   /telegram/webhook            (bot inbound: /follow, /unfollow, /list)
POST   /trip-search                 { origin_airport, destinations?, date_range_start, date_range_end, min_nights, max_nights, max_budget_total }
GET    /trip-search/{id}/results
POST   /trip-search/{id}/track      { interval_minutes }
DELETE /trip-search/{id}/track
GET    /trip/{id}
```

## Deployment
- VPS, publicly reachable over HTTPS via Nginx + Let's Encrypt.
- Secrets only via .env, never committed to the repo.
- Docker Compose brings up the full stack: frontend, backend, worker, scheduler, Postgres, Redis, Nginx.
- Telegram webhook endpoint must be reachable over HTTPS (satisfied by the VPS + Nginx TLS setup).

## Testing
- Unit tests for business logic, including the Tracking Service and diffing logic.
- Integration tests for API and for the Telegram webhook handler (mocked Telegram API).
- Provider contract tests, run against recorded/mocked fixtures — never against live Booking/Airbnb in CI.
- Notifier contract tests (mocked Telegram API).

## Logging
Structured JSON logging.

## Risk Notes
Scraping Booking, Airbnb, Google Flights and Skyscanner likely runs counter to their Terms of Service; this is knowingly accepted for personal, non-commercial use. Providers should throttle requests and degrade gracefully (skip, log, continue) rather than retry aggressively into a block, to reduce the chance of IP/account bans. Flight sites in particular have stricter bot detection than hotel sites — expect a higher block rate; a failed flight-explore cycle must be skipped entirely (no accommodation scraping wasted on a cycle with no valid flight data).

**Two-stage pipeline rule (trip search):** never brute-force accommodation checks across every candidate destination/date combination. Always narrow via `FlightProvider.explore()` first (top N cheapest candidates, N capped e.g. at 15–20), and only run accommodation scraping against that shortlist.

## Definition of Done
Feature includes tests, typing, documentation and Docker compatibility.
