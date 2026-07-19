# Tasks: Accommodation Search MVP

**Input**: Design documents from `specs/001-accommodation-search-mvp/`
**Branch**: `001-accommodation-search-mvp`
**Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md) | **Data Model**: [data-model.md](data-model.md)
**Contracts**: [contracts/api.md](contracts/api.md) | [contracts/provider-interface.md](contracts/provider-interface.md)

## Format: `[ID] [P?] [Story?] Description with file path`

- **[P]**: Can run in parallel (different files, no dependencies on other in-progress tasks)
- **[Story]**: User story this task belongs to (US1–US4)
- Tasks without a Story label are Setup or Foundational

---

## Phase 1: Setup (Project Initialization)

**Purpose**: Create the project skeleton — directories, tooling config, Docker infrastructure.
No business logic; just runnable empty shells.

- [ ] T001 Create backend project structure: `backend/app/{api,services,providers,notifiers,workers,models,repositories,schemas,core}/` with `__init__.py` files
- [ ] T002 Create `backend/pyproject.toml` with all dependencies: fastapi, uvicorn, sqlalchemy[asyncio], alembic, asyncpg, pydantic-settings, pydantic[email], python-jose[cryptography], argon2-cffi, playwright, arq, structlog, httpx; dev: pytest, pytest-asyncio, pytest-cov
- [ ] T003 [P] Create `frontend/` with Vite + React 19 + TypeScript strict: run `npm create vite@latest frontend -- --template react-ts`, configure `tsconfig.json` with `"strict": true`, install axios, react-query, react-router-dom
- [ ] T004 [P] Create `docker-compose.yml` with all 7 services: frontend (port 3000), backend (port 8000), worker, scheduler, db (PostgreSQL, port 5432), redis (port 6379), nginx (port 80/443)
- [ ] T005 [P] Create `docker/backend/Dockerfile`: python 3.13-slim, install dependencies via pyproject.toml, run alembic upgrade head then uvicorn on startup
- [ ] T006 [P] Create `docker/frontend/Dockerfile`: node 20-alpine, npm ci, npm run build; nginx serve static
- [ ] T007 [P] Create `docker/nginx/nginx.conf`: proxy `/api/` → backend:8000, `/` → frontend:80; TLS termination placeholder; `proxy_read_timeout 200s` for long-running scrapes
- [ ] T008 Create `.env.example` at project root with all variables from quickstart.md: `DATABASE_URL`, `REDIS_URL`, `JWT_SECRET`, `JWT_ALGORITHM`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_WEBHOOK_SECRET`, `PROXY_PROVIDER_HOST/USER/PASS`, `CORS_ORIGINS`

**Checkpoint**: `docker compose build` completes without errors.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure every user story depends on — config, auth, database setup,
provider/notifier interfaces, and frontend auth shell. No user story work begins until this
phase is complete.

**⚠️ CRITICAL**: All user stories are blocked until Phase 2 is complete.

### Backend Core

- [ ] T009 Implement `backend/app/core/config.py`: pydantic-settings `Settings` class reading all `.env` variables; expose singleton `get_settings()`
- [ ] T010 Setup structlog in `backend/app/core/logging.py`: JSON renderer in production, console in dev; request-ID context var; configure in `app/main.py`
- [ ] T011 Create `backend/app/main.py`: FastAPI app instance, CORS middleware (origins from settings), exception handlers (return RFC 7807 Problem Details for HTTPException + validation errors), include all routers
- [ ] T012 Setup Alembic in `backend/alembic/`: `alembic.ini`, `env.py` using async SQLAlchemy engine from settings; `backend/app/core/database.py` with `AsyncSessionLocal` and `get_db()` dependency

### Backend Auth (Foundational — all stories need authenticated users)

- [ ] T013 Create `backend/app/models/user.py`: SQLAlchemy 2.x `User` model with all columns from data-model.md (id UUID PK, email unique, hashed_password, telegram_chat_id, is_active, created_at, updated_at)
- [ ] T014 Implement `backend/app/core/security.py`: Argon2id `hash_password()`/`verify_password()`; HS256 JWT `create_access_token()`/`create_refresh_token()`/`decode_token()`; refresh token cookie helpers
- [ ] T015 Implement `backend/app/services/auth_service.py`: `authenticate_user()`, `create_tokens()`, `refresh_access_token()`, `revoke_refresh_token()` (Redis-backed revocation list)
- [ ] T016 [P] Create `backend/app/schemas/auth.py`: Pydantic v2 `LoginRequest`, `TokenResponse` (no hashed_password), `RefreshResponse`
- [ ] T017 Implement `backend/app/api/v1/routes/auth.py`: `POST /auth/login`, `POST /auth/refresh`, `POST /auth/logout`; set/clear HttpOnly refresh token cookie
- [ ] T018 Implement `backend/app/api/v1/deps.py`: `get_current_user()` dependency; `get_db()` re-export; rate-limit stub for login endpoint
- [ ] T019 Create first Alembic migration in `backend/alembic/versions/`: create `users` table; verify `alembic upgrade head` + `alembic downgrade -1` cycle works
- [ ] T020 Setup Redis async client in `backend/app/core/redis.py`: `get_redis()` dependency; connection pool from `REDIS_URL` setting

### Provider & Notifier Interfaces

- [ ] T021 [P] Implement `backend/app/providers/base.py`: `ScrapeStatus` enum, `PropertyListing`, `SearchResult`, `PropertyDetail`, `ParsedPropertySearch` dataclasses, `Provider` ABC — exact types from contracts/provider-interface.md
- [ ] T022 [P] Implement `backend/app/notifiers/base.py`: `NotificationType` enum, `NotificationMessage` dataclass, `Notifier` ABC — exact types from contracts/provider-interface.md

### Frontend Auth Shell

- [ ] T023 Create `frontend/src/api/client.ts`: Axios instance with base URL `/api/v1`, request interceptor injecting in-memory access token, response interceptor handling 401 → POST /auth/refresh → retry once → redirect to /login
- [ ] T024 Implement `frontend/src/hooks/useAuth.ts`: in-memory access token store (React state only — never localStorage/sessionStorage), `login()`, `logout()`, `isAuthenticated` flag
- [ ] T025 Implement `frontend/src/components/ProtectedRoute.tsx`: wraps all routes except `/login`; redirects unauthenticated users to `/login`
- [ ] T026 Implement `frontend/src/pages/LoginPage.tsx`: email + password form, POST /auth/login, redirect to `/search` on success, show error on 401
- [ ] T027 Configure `frontend/src/main.tsx`: React Router with ProtectedRoute wrapping all non-login routes; React Query `QueryClientProvider`

### Test Infrastructure

- [ ] T028 [P] Setup `backend/tests/conftest.py`: pytest-asyncio, async test DB (separate `DATABASE_URL_TEST` env var), `AsyncClient` fixture for FastAPI app, `db_session` fixture with rollback-per-test, `redis_mock` fixture
- [ ] T029 [P] Setup `frontend/tests/`: Vitest config in `vite.config.ts`, `@testing-library/react` install, `frontend/tests/setup.ts` for global mocks

**Checkpoint**: `POST /auth/login` returns a JWT; `GET /` on frontend redirects to `/login`; all auth unit tests pass.

---

## Phase 3: User Story 1 — Search & Compare Listings (Priority: P1) 🎯 MVP

**Goal**: User can search Booking + Airbnb simultaneously, see a merged sortable/filterable
results table, and export CSV.

**Independent Test**: Log in → submit search form → see progress → merged results table
with both providers → sort by price → export CSV. Testable with mocked providers.

### Models & Migrations

- [ ] T030 [P] [US1] Create `backend/app/models/property.py`: `Property` SQLAlchemy model per data-model.md (id, provider, provider_property_id, name, url, location, lat/lon, bedrooms, bathrooms, amenities JSONB, timestamps); unique constraint `(provider, provider_property_id)`
- [ ] T031 [P] [US1] Create `backend/app/models/search.py`: `Search` and `SearchResult` SQLAlchemy models per data-model.md; `status` enum column; `filters` JSONB; FK to User and Property
- [ ] T032 [US1] Create Alembic migration for `properties`, `searches`, `search_results` tables; verify upgrade + downgrade

### Provider Contract Tests (run against recorded fixtures — never live)

- [ ] T033 [P] [US1] Create `backend/tests/contract/fixtures/booking/`: record a sample Booking search response HTML; create `backend/tests/contract/test_booking_provider.py` asserting `SearchResult.status == OK`, correct `PropertyListing` field types, `ScrapeStatus.BLOCKED` returned on fixture with challenge page
- [ ] T034 [P] [US1] Create `backend/tests/contract/fixtures/airbnb/`: record a sample Airbnb search response; create `backend/tests/contract/test_airbnb_provider.py` asserting same shape + `parse_url()` correctly extracts dates from a sample Airbnb URL

### Provider Implementations

- [ ] T035 [US1] Implement `backend/app/providers/booking.py`: `BookingProvider` implementing `Provider` ABC; Playwright async per-job browser context with proxy from settings; `search()` scrapes listing grid, returns `SearchResult`; `details()` scrapes property page for price; `parse_url()` extracts `check_in`/`check_out` from URL params; `normalize()` maps raw dict → `PropertyListing`; returns `ScrapeStatus.BLOCKED/CAPTCHA/INCOMPLETE` on failure — never raises
- [ ] T036 [US1] Implement `backend/app/providers/airbnb.py`: `AirbnbProvider` implementing `Provider` ABC; same structure as BookingProvider; Airbnb-specific DOM selectors and URL patterns

### Repositories & Schemas

- [ ] T037 [P] [US1] Implement `backend/app/repositories/property_repository.py`: `upsert_property()` (insert or update by provider+provider_property_id), `get_by_id()`
- [ ] T038 [P] [US1] Implement `backend/app/repositories/search_repository.py`: `create_search()`, `update_status()`, `add_results()`, `get_results_page()` (with sort/filter params)
- [ ] T039 [P] [US1] Create `backend/app/schemas/search.py`: Pydantic v2 `SearchRequest`, `SearchStatusResponse`, `PropertyListingResponse` (no internal fields), `SearchResultsPage`, `ProviderStatus`

### Search Service & Routes

- [ ] T040 [US1] Implement `backend/app/services/search_service.py`: `run_search()` calls both providers concurrently via `asyncio.gather()` (only through `Provider` interface), stores status in Redis, upserts properties, writes `SearchResult` rows; `get_status()` reads Redis + DB counts; `get_results_page()` queries with sort/filter; `export_csv()` streams all results as CSV
- [ ] T041 [US1] Implement `backend/app/api/v1/routes/search.py`: `POST /search` (202, enqueue async task), `GET /search/{id}/status`, `GET /search/{id}/results` (paginated, sortable), `GET /search/{id}/export.csv` (StreamingResponse `text/csv`)

### Integration Tests

- [ ] T042 [P] [US1] Create `backend/tests/integration/test_search_api.py`: mock `BookingProvider` and `AirbnbProvider` (return fixture `SearchResult`); test: search returns 202 → status polling → results page contains merged listings → export CSV returns text/csv with correct row count; test provider-failure scenario (one provider returns BLOCKED → other results still shown)

### Frontend

- [ ] T043 [P] [US1] Create `frontend/src/api/search.ts`: React Query hooks `useStartSearch()`, `useSearchStatus()` (polls every 3s while running), `useSearchResults()` (paginated), `useExportCsv()` (anchor href)
- [ ] T044 [P] [US1] Create `frontend/src/pages/SearchPage.tsx`: destination input, date pickers (check-in/check-out), guest count, provider checkboxes (Booking/Airbnb/Both), filter panel (price range, bedrooms, bathrooms, rating, amenities checkboxes: free cancellation, kitchen, wifi, AC, pool); submit → POST /search → redirect to progress page
- [ ] T045 [P] [US1] Create `frontend/src/pages/SearchProgressPage.tsx`: polls `useSearchStatus()` every 3s; shows per-provider progress (running/complete/failed); auto-redirects to results when `status === 'complete'`; shows provider failure notice if one provider failed
- [ ] T046 [US1] Create `frontend/src/pages/SearchResultsPage.tsx`: sortable table (click column header cycles asc/desc); client-side column filter inputs; Source column with provider badge; per-row Track toggle (enabled only after Phase 4); "Track this search" button (enabled after Phase 4); "Export CSV" anchor button; meaningful empty state when zero results
- [ ] T047 [P] [US1] Create `frontend/src/pages/PropertyDetailPage.tsx`: property details view (name, price, rating, amenities, map placeholder, link to provider); "Track this property" button (enabled after Phase 5)

**Checkpoint**: Full search flow works end-to-end with mocked providers. CSV download works. All integration tests pass.

---

## Phase 4: User Story 2 — Track a Saved Search (Priority: P2)

**Goal**: User can save a search to re-run in the background; receives Telegram alerts for
new listings and price drops below the lowest-ever recorded price.

**Independent Test**: Track a search → simulate background worker cycle finding a new listing
→ verify `NotificationLog` row created and `TelegramNotifier.send()` called with correct
message. Testable with mocked providers and mocked Telegram API.

### Models & Migrations

- [ ] T048 [P] [US2] Create `backend/app/models/tracked_search.py`: `TrackedSearch`, `TrackedSearchSeenProperty` SQLAlchemy models per data-model.md; unique constraints; `interval_hours` check constraint IN (6,12,24,48); index on `(is_active, next_run_at)`
- [ ] T049 [P] [US2] Create `backend/app/models/notification_log.py`: `NotificationLog` SQLAlchemy model per data-model.md; `PriceSnapshot` model; indexes on `(user_id, sent_at DESC)` and `(property_id)` 
- [ ] T050 [US2] Create Alembic migration for `tracked_searches`, `tracked_search_seen_properties`, `notification_logs`, `price_snapshots` tables

### Notifier Implementation

- [ ] T051 [US2] Implement `backend/app/notifiers/telegram.py`: `TelegramNotifier` implementing `Notifier` ABC; `send()` calls Telegram Bot API `sendMessage` via httpx async; formats `price_drop` and `new_listing` messages with property name, prices, and URL; returns False on API error — never raises; `TELEGRAM_BOT_TOKEN` from settings

### Repositories & Schemas

- [ ] T052 [P] [US2] Implement `backend/app/repositories/tracking_repository.py`: `create_tracked_search()`, `remove_tracked_search()`, `get_active_tracked_searches()`, `get_overdue_tracked_searches()` (next_run_at ≤ now), `update_seen_properties()`, `get_seen_properties()`, count queries for per-user limits
- [ ] T053 [P] [US2] Implement `backend/app/repositories/notification_repository.py`: `create_notification_log()`, `get_notifications_page()` (scoped to user_id, paginated)
- [ ] T054 [P] [US2] Create `backend/app/schemas/tracked_search.py`: `CreateTrackedSearchRequest` (search_id, interval_hours), `TrackedSearchResponse`, `TrackedSearchListResponse`
- [ ] T055 [P] [US2] Create `backend/app/schemas/notification.py`: `NotificationResponse`, `NotificationListResponse` (price_before, price_after, type, sent_at, property_name, property_url)

### Tracking Service

- [ ] T056 [US2] Implement `backend/app/services/tracking_service.py`: `create_tracked_search()` (count check → 10-item limit → upsert if duplicate, FR-016), `remove_tracked_search()`, interval validation (must be in {6,12,24,48}); check `telegram_chat_id` to emit no-telegram warning in response; raise `TrackingLimitExceededError` on overflow

### Diff Logic & Search Worker

- [ ] T057 [US2] Implement diff logic in `backend/app/workers/search_worker.py`: `compute_search_diff(current_listings, seen_properties) → list[DiffEvent]`; `DiffEvent` is `NewListing` or `PriceDrop`; `PriceDrop` fires only if current_price < `min_price_seen`; returns empty list if current listings set is empty (safe-discard: worker checks `SearchResult.status == OK` before calling diff)
- [ ] T058 [US2] Implement arq job `rerun_tracked_search()` in `backend/app/workers/search_worker.py`: fetch overdue tracked searches → for each: run provider search via interface → if status != OK discard entirely (no DB writes, no notifications, log warning) → compute diff → for each diff event: write `NotificationLog`, write `PriceSnapshot`, call `Notifier.send()` if user.telegram_chat_id set → update `TrackedSearchSeenProperty` baseline → update `next_run_at`

### Routes

- [ ] T059 [US2] Implement `backend/app/api/v1/routes/tracked_search.py`: `POST /tracked-searches` (calls TrackingService, returns 422 with clear message on limit exceeded), `GET /tracked-searches`, `DELETE /tracked-searches/{id}`
- [ ] T060 [US2] Implement `backend/app/api/v1/routes/notifications.py`: `GET /notifications` (paginated, filterable by type, always scoped to authenticated user)

### arq Scheduler Setup

- [ ] T061 [US2] Create `backend/app/workers/scheduler.py`: arq `WorkerSettings` with cron job `rerun_tracked_search` polling every 5 minutes; worker reads `REDIS_URL` from settings; ensure docker-compose `scheduler` service runs this

### Unit & Integration Tests

- [ ] T062 [P] [US2] Create `backend/tests/unit/test_tracking_service.py`: test `create_tracked_search()` success, duplicate (returns existing), limit-exceeded raises `TrackingLimitExceededError`, invalid interval raises; test `remove_tracked_search()` not-found 404; all tests use mocked DB
- [ ] T063 [P] [US2] Create `backend/tests/unit/test_search_diff.py`: test `compute_search_diff()` — empty baseline (all new), no-new (no events), price-drop below min, price-drop above min (no event), empty current listings (safe-discard check)
- [ ] T064 [P] [US2] Create `backend/tests/integration/test_tracked_search_api.py`: POST creates tracked search → GET lists it → DELETE removes it; 422 on invalid interval; 422 on 11th tracked search; GET /notifications returns history
- [ ] T065 [P] [US2] Create `backend/tests/contract/test_telegram_notifier.py`: mock httpx; assert `TelegramNotifier.send()` sends correct `sendMessage` payload for `price_drop` and `new_listing`; assert returns False (not raises) on Telegram API 400 error

### Frontend

- [ ] T066 [P] [US2] Create `frontend/src/api/tracked.ts`: `useCreateTrackedSearch()` mutation, `useTrackedSearches()` query, `useDeleteTrackedSearch()` mutation, `useNotifications()` query
- [ ] T067 [US2] Wire "Track this search" button in `frontend/src/pages/SearchResultsPage.tsx`: opens interval selector modal (6h/12h/24h/48h dropdown), calls `useCreateTrackedSearch()`, shows warning if Telegram not linked (FR-005 clarification), shows 422 error message on limit exceeded
- [ ] T068 [US2] Create `frontend/src/pages/TrackedDashboardPage.tsx`: two sections — "Tracked Searches" and "Tracked Properties" (stub for US3); each row shows destination/property name, interval, last-checked time, next-run time, status badge; Untrack button calls DELETE
- [ ] T069 [P] [US2] Create `frontend/src/pages/NotificationHistoryPage.tsx`: paginated list of all past alerts (type badge, property name linked to URL, price before → after with arrow, timestamp); always accessible regardless of Telegram link status; meaningful empty state

**Checkpoint**: TrackedSearch CRUD works. Background worker fires diff and creates NotificationLog rows. Integration tests with mocked providers and mocked Telegram API pass.

---

## Phase 5: User Story 3 — Follow a Specific Listing via Telegram Bot (Priority: P3)

**Goal**: User sends `/follow <url>` to the bot and it tracks that exact property for the
dates in the URL; alerts when price drops below the lowest-ever recorded price.

**Independent Test**: Send mocked Telegram `/follow <booking_url_with_dates>` to the webhook
endpoint → `TrackedProperty` row created → simulate property worker cycle with lower price
→ `NotificationLog` row created and `TelegramNotifier.send()` called.

### Models & Migrations

- [ ] T070 [P] [US3] Create `backend/app/models/tracked_property.py`: `TrackedProperty` SQLAlchemy model per data-model.md; unique `(user_id, property_id, check_in, check_out)`; index on `(is_active, next_run_at)` and `(user_id, check_in)` for auto-deactivation sweep; `min_price_seen` NUMERIC
- [ ] T071 [US3] Create Alembic migration for `tracked_properties` table

### TrackingService Extensions

- [ ] T072 [US3] Add to `backend/app/services/tracking_service.py`: `create_tracked_property()` (count check → 20-item limit, FR-016; parse URL via `Provider.parse_url()` to get property identity + dates; upsert if duplicate), `remove_tracked_property()`; add `TrackedProperty` count query to tracking_repository.py

### Property Worker

- [ ] T073 [US3] Implement arq job `recheck_tracked_property()` in `backend/app/workers/property_worker.py`: fetch overdue tracked properties → for each: call `Provider.details()` via interface → if status != OK discard entirely → compare current_price < `min_price_seen` → if price-drop: write `NotificationLog`, write `PriceSnapshot`, call `Notifier.send()` if linked → update `min_price_seen`, `next_run_at` → auto-deactivate if `check_in <= today()` (FR-014)
- [ ] T074 [US3] Add `recheck_tracked_property` cron job to `backend/app/workers/scheduler.py` (every 5 minutes alongside search worker)

### Tracked Property Routes

- [ ] T075 [US3] Implement `backend/app/api/v1/routes/tracked_property.py`: `POST /tracked-properties`, `GET /tracked-properties`, `DELETE /tracked-properties/{id}`; add to router in main.py

### Telegram Webhook Infrastructure

- [ ] T076 [US3] Implement `backend/app/api/v1/routes/telegram.py`: `POST /telegram/webhook` — validate `X-Telegram-Bot-Api-Secret-Token` header (return 403 if invalid or missing); parse Telegram `Update` object; route to command handler; always return 200
- [ ] T077 [US3] Implement bot command handler `backend/app/services/telegram_bot_service.py`: `/follow <url>` — call `Provider.parse_url()` for each registered provider until one returns non-None; if no provider matches → reply error; if no dates in URL → reply asking to resend with dates; else call `TrackingService.create_tracked_property()` → reply confirmation; `/unfollow <url>` — find and remove tracked property → reply confirmation or "not tracked"

### Schemas

- [ ] T078 [P] [US3] Create `backend/app/schemas/tracked_property.py`: `CreateTrackedPropertyRequest`, `TrackedPropertyResponse`, `TrackedPropertyListResponse`

### Integration Tests

- [ ] T079 [P] [US3] Create `backend/tests/integration/test_tracked_property_api.py`: POST creates tracked property, GET lists, DELETE removes; 422 on limit exceeded; 422 on duplicate (returns existing)
- [ ] T080 [P] [US3] Create `backend/tests/integration/test_telegram_webhook.py`: valid signature + `/follow` valid URL → TrackedProperty created, reply sent; valid signature + `/follow` no-dates URL → reply asking for dates; valid signature + `/follow` unrecognized URL → error reply; invalid signature → 403; `/unfollow` valid → removed; unlinked chat → no data returned
- [ ] T081 [P] [US3] Create `backend/tests/unit/test_property_worker.py`: price-drop below min_price_seen → notification created; price above min → no notification; status BLOCKED → discard (no DB write); check_in passed → is_active set false

### Frontend

- [ ] T082 [P] [US3] Create `frontend/src/api/tracked.ts` additions: `useCreateTrackedProperty()` mutation, `useTrackedProperties()` query, `useDeleteTrackedProperty()` mutation
- [ ] T083 [US3] Wire "Track this property" button in `frontend/src/pages/PropertyDetailPage.tsx`: interval selector modal (6h/12h/24h/48h), calls `useCreateTrackedProperty()`, shows warning if Telegram not linked, shows 422 error on limit exceeded
- [ ] T084 [US3] Wire per-row Track toggle in `frontend/src/pages/SearchResultsPage.tsx`: clicking "Track" on a result row creates a TrackedProperty for those search dates; toggle shows "Tracking" state if already tracked
- [ ] T085 [US3] Add Tracked Properties section to `frontend/src/pages/TrackedDashboardPage.tsx`: list of active tracked properties with property name, check-in/check-out, interval, min_price_seen, last-checked, untrack button

**Checkpoint**: `/follow` via Telegram webhook creates a TrackedProperty. Property worker detects price drops and creates NotificationLog rows. Auto-deactivation works. All webhook integration tests pass.

---

## Phase 6: User Story 4 — Account & Telegram Linking (Priority: P4)

**Goal**: User links their Telegram account via a one-time code deep-link; `/list` shows
their tracked items; unlinking removes the link.

**Independent Test**: Generate link code → simulate `/start <code>` via webhook → User row
has `telegram_chat_id` set → `/list` returns tracked items → unlink clears `telegram_chat_id`.

### Linking Backend

- [ ] T086 [US4] Implement `/start <code>` handling in `backend/app/services/telegram_bot_service.py`: look up `telegram_link:<code>` key in Redis → if found: set `user.telegram_chat_id = update.message.chat.id`, set `telegram_linked_at`, delete code from Redis, reply confirming link → if not found (expired/already used): reply "link code expired or already used"
- [ ] T087 [US4] Implement `POST /telegram/link-code` in `backend/app/api/v1/routes/telegram.py`: generate 8-char random code, store `telegram_link:<code> → user_id` in Redis with 900s TTL, return `{code, expires_in_seconds: 900, deep_link}`
- [ ] T088 [US4] Implement `DELETE /telegram/link` in `backend/app/api/v1/routes/telegram.py`: set `user.telegram_chat_id = NULL`, set `telegram_linked_at = NULL`; return 204
- [ ] T089 [US4] Implement `/list` bot command in `backend/app/services/telegram_bot_service.py`: look up user by `telegram_chat_id`; if not found reply "send /start to link your account"; else query `TrackingService` for active tracked searches and properties; format and reply with list (truncated to 10 items if more)

### Schemas

- [ ] T090 [P] [US4] Add `LinkCodeResponse` to `backend/app/schemas/auth.py` (or new `telegram.py` schema file): `{code: str, expires_in_seconds: int, deep_link: str}`

### Integration Tests

- [ ] T091 [P] [US4] Create `backend/tests/integration/test_telegram_linking.py`: POST /telegram/link-code returns code + deep_link; simulate `/start <code>` via webhook → user.telegram_chat_id set; second use of same code → "expired" reply (code deleted after first use); DELETE /telegram/link clears chat_id; /list returns tracked items for linked user; /list for unlinked chat returns "link first" reply

### Frontend

- [ ] T092 [P] [US4] Create `frontend/src/api/telegram.ts`: `useGenerateLinkCode()` mutation, `useUnlinkTelegram()` mutation, `useCurrentUser()` query (to check `telegram_chat_id` presence)
- [ ] T093 [US4] Create `frontend/src/pages/TelegramLinkPage.tsx` at `/settings/telegram`: if not linked → "Generate code" button → shows code + deep-link button + QR placeholder + 15-minute countdown; if linked → shows "Linked as @username" (if available) + "Unlink" button; calls `useUnlinkTelegram()` on confirm; update `useAuth` to expose `telegramLinked` flag used in FR-005 warning

**Checkpoint**: Full Telegram linking flow works end-to-end. `/list` returns tracked items for linked users. Unlink clears the association. One-time code cannot be reused.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Security hardening, operational readiness, typing checks, Docker Compose gate.

- [ ] T094 [P] Run `mypy --strict` on all `backend/app/` code and fix all type errors
- [ ] T095 [P] Run `ruff check` + `ruff format` on all backend code; fix all warnings
- [ ] T096 [P] Run `tsc --noEmit` on `frontend/src/`; fix all TypeScript strict errors; remove any `any` types
- [ ] T097 Add brute-force rate limiting to `POST /auth/login` in `backend/app/api/v1/routes/auth.py`: max 10 attempts per IP per 10 minutes using Redis counter
- [ ] T098 Add per-user data isolation assertions to `backend/tests/integration/`: parametrized test that creates two users and verifies neither can see the other's TrackedSearch, TrackedProperty, NotificationLog, or PriceSnapshot records
- [ ] T099 Add security headers to Nginx config in `docker/nginx/nginx.conf`: `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin`, `Content-Security-Policy` base policy
- [ ] T100 Validate `docker compose up --build` starts all 7 services cleanly: write smoke-test script `scripts/smoke-test.sh` that waits for backend `/api/v1/openapi.json` to return 200 and frontend `/` to return 200
- [ ] T101 [P] Run through quickstart.md end-to-end in a fresh Docker Compose environment and fix any gaps found

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1** (Setup): No dependencies — start immediately
- **Phase 2** (Foundational): Depends on Phase 1 — BLOCKS all user story phases
- **Phase 3** (US1): Depends on Phase 2 — first to unblock after Foundational
- **Phase 4** (US2): Depends on Phase 2 + Phase 3 (needs Search and SearchResult to exist for TrackedSearch)
- **Phase 5** (US3): Depends on Phase 2 + Phase 4 (TrackingService scaffolded, TelegramNotifier implemented, Telegram webhook endpoint shared)
- **Phase 6** (US4): Depends on Phase 2 + Phase 5 (Telegram webhook endpoint already exists)
- **Phase 7** (Polish): Depends on all story phases complete

### User Story Dependencies

- **US1 (P1)**: Can start after Foundational — no dependency on other stories
- **US2 (P2)**: Can start after Foundational + US1 complete (TrackedSearch references search_id)
- **US3 (P3)**: Requires Phase 4 complete (TrackingService exists, TelegramNotifier available, Telegram webhook infrastructure can be added incrementally)
- **US4 (P4)**: Requires Phase 5 complete (webhook endpoint already set up; adds /start handler + linking UI)

### Within Each Phase

- Models before repositories before services before routes
- Backend tests can run in parallel with other backend tasks marked [P]
- Frontend tasks marked [P] can run in parallel with each other
- Backend and frontend tasks for the same story can run in parallel (different files)

---

## Parallel Opportunities per Story

### Phase 3 (US1) — can parallelise immediately after T032:
```
T033 BookingProvider contract test
T034 AirbnbProvider contract test
T035 Search schemas
T037 PropertyRepository
T038 SearchRepository
T043 frontend/src/api/search.ts
T044 SearchPage
T045 SearchProgressPage
T047 PropertyDetailPage
```
Then sequentially: T035 → T040 (SearchService) → T041 (routes) → T042 (integration tests) → T046 (SearchResultsPage — needs API shape)

### Phase 4 (US2) — can parallelise after T050:
```
T052 TrackingRepository
T053 NotificationRepository
T054 TrackedSearch schemas
T055 Notification schemas
T062 unit test: TrackingService
T063 unit test: diff logic
T065 contract test: TelegramNotifier
T066 frontend/src/api/tracked.ts
T069 NotificationHistoryPage
```

---

## Implementation Strategy

### MVP (User Story 1 Only)

1. Complete Phase 1 (Setup)
2. Complete Phase 2 (Foundational)
3. Complete Phase 3 (US1 — Search)
4. **STOP AND VALIDATE**: `docker compose up` → login → search Barcelona 2 nights → merged results table → export CSV
5. Deploy/demo US1 independently

### Incremental Delivery

1. Phase 1 + 2 → Foundation working (login, empty app)
2. + Phase 3 (US1) → Live search with CSV export *(MVP)*
3. + Phase 4 (US2) → Background tracking with Telegram price-drop alerts
4. + Phase 5 (US3) → `/follow` bot command tracking
5. + Phase 6 (US4) → Telegram linking UI + `/list` command
6. + Phase 7 → Production-hardened, all gates passing

### Agent Team Strategy (with `run-agents.sh`)

Once Foundational is complete:
- **backend-developer-python** → US1 backend (T030–T042)
- **frontend-developer-react** → US1 frontend (T043–T047) in parallel
- After US1: backend continues US2 while frontend builds TrackedDashboard and NotificationHistory
- **autotester** → contract tests (T033, T034, T065) and integration tests can be driven in parallel with implementation

---

## Notes

- `[P]` tasks have different file targets and no blocking in-progress dependencies — safe to run concurrently
- Each Story label maps directly to a user story in spec.md for traceability
- Safe-discard invariant (FR-013) is enforced in T057 and T073 — these are release blockers per autotester.md
- Per-user data isolation (FR-015) validated explicitly in T098
- `hashed_password` MUST appear in NO Pydantic response schema — verify in T094 (mypy) and T098
- Commit after each phase checkpoint at minimum; prefer after each task group
- All provider and notifier tests use mocked/recorded fixtures — no live Booking/Airbnb/Telegram calls in CI
