# Data Model: Accommodation Search MVP

**Branch**: `001-accommodation-search-mvp` | **Date**: 2026-07-19

All tables use UUID primary keys and `TIMESTAMPTZ` for timestamps. All migrations managed
by Alembic. All models mapped via SQLAlchemy 2.x declarative style.

---

## Entity: User

Represents a provisioned account. No public self-registration.

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | UUID | PK |
| `email` | VARCHAR(255) | UNIQUE, NOT NULL |
| `hashed_password` | TEXT | NOT NULL (Argon2id) |
| `telegram_chat_id` | BIGINT | NULLABLE, UNIQUE |
| `telegram_linked_at` | TIMESTAMPTZ | NULLABLE |
| `is_active` | BOOLEAN | NOT NULL, DEFAULT true |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() |
| `updated_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() |

**Rules**:
- `hashed_password` MUST never appear in any Pydantic response schema.
- `telegram_chat_id` is set during the bot linking flow; NULL means unlinked.

---

## Entity: Search

A single one-time search execution with its parameters and results reference. Results
are not stored as rows — they are held in Redis during execution (keyed by `id`) and
discarded after the session window.

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | UUID | PK |
| `user_id` | UUID | FK → User.id, NOT NULL |
| `destination` | TEXT | NOT NULL |
| `check_in` | DATE | NOT NULL |
| `check_out` | DATE | NOT NULL |
| `guests` | SMALLINT | NOT NULL, DEFAULT 1 |
| `providers` | VARCHAR[] | NOT NULL (e.g., ['booking','airbnb']) |
| `filters` | JSONB | NULLABLE (bedrooms, bathrooms, price_min, price_max, rating_min, amenities[]) |
| `status` | VARCHAR(20) | NOT NULL: pending\|running\|partial\|complete\|failed |
| `result_count` | INTEGER | NULLABLE |
| `provider_statuses` | JSONB | NULLABLE (per-provider status + result count) |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() |
| `completed_at` | TIMESTAMPTZ | NULLABLE |

**Rules**:
- Results are ephemeral (Redis-cached during execution); `Search` row is the durable record
  of what was searched and its final status.
- `filters` JSONB allows adding new filter types without schema migration.

---

## Entity: Property

A normalized, de-duplicated accommodation listing. Properties are upserted on scrape;
identity key is `(provider, provider_property_id)`.

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | UUID | PK |
| `provider` | VARCHAR(50) | NOT NULL ('booking'\|'airbnb') |
| `provider_property_id` | TEXT | NOT NULL |
| `name` | TEXT | NOT NULL |
| `url` | TEXT | NOT NULL |
| `location` | TEXT | NULLABLE |
| `latitude` | NUMERIC(9,6) | NULLABLE |
| `longitude` | NUMERIC(9,6) | NULLABLE |
| `bedrooms` | SMALLINT | NULLABLE |
| `bathrooms` | SMALLINT | NULLABLE |
| `amenities` | JSONB | NULLABLE |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() |
| `updated_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() |

**Unique constraint**: `(provider, provider_property_id)`.

---

## Entity: SearchResult

Links a Search execution to the Properties it returned, with the price observed at that
search run.

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | UUID | PK |
| `search_id` | UUID | FK → Search.id, NOT NULL |
| `property_id` | UUID | FK → Property.id, NOT NULL |
| `price_per_night` | NUMERIC(10,2) | NOT NULL |
| `total_price` | NUMERIC(10,2) | NOT NULL |
| `rating` | NUMERIC(3,2) | NULLABLE |
| `distance_km` | NUMERIC(6,2) | NULLABLE |
| `free_cancellation` | BOOLEAN | NULLABLE |
| `raw_snapshot` | JSONB | NULLABLE (full scraped data for debugging) |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() |

---

## Entity: TrackedSearch

A saved search that re-runs periodically. Owns the per-property baseline (seen set + minimum
prices) used by the diff worker.

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | UUID | PK |
| `user_id` | UUID | FK → User.id, NOT NULL |
| `search_id` | UUID | FK → Search.id, NOT NULL (the originating search) |
| `interval_hours` | SMALLINT | NOT NULL, CHECK IN (6,12,24,48) |
| `is_active` | BOOLEAN | NOT NULL, DEFAULT true |
| `last_successful_run_at` | TIMESTAMPTZ | NULLABLE |
| `next_run_at` | TIMESTAMPTZ | NOT NULL |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() |
| `updated_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() |

**Unique constraint**: `(user_id, search_id)` — no duplicate tracking of the same search.

**Rules**:
- Per-user limit: max 10 active rows where `user_id = X AND is_active = true`.
- `next_run_at` is set to `now() + interval_hours` after each successful cycle.
- Workers only process rows where `is_active = true AND next_run_at <= now()`.

---

## Entity: TrackedSearchSeenProperty

The baseline for a tracked search: the set of properties seen in the last successful cycle
and their minimum recorded prices. Used by the diff worker to detect new listings and
price drops.

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | UUID | PK |
| `tracked_search_id` | UUID | FK → TrackedSearch.id, NOT NULL |
| `property_id` | UUID | FK → Property.id, NOT NULL |
| `min_price_seen` | NUMERIC(10,2) | NOT NULL |
| `first_seen_at` | TIMESTAMPTZ | NOT NULL |
| `last_seen_at` | TIMESTAMPTZ | NOT NULL |

**Unique constraint**: `(tracked_search_id, property_id)`.

**Rules**:
- Updated ONLY on a successful (non-discarded) scrape cycle.
- A discarded cycle MUST NOT write to this table.

---

## Entity: TrackedProperty

A specific property being monitored for price drops on specific dates.

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | UUID | PK |
| `user_id` | UUID | FK → User.id, NOT NULL |
| `property_id` | UUID | FK → Property.id, NOT NULL |
| `check_in` | DATE | NOT NULL |
| `check_out` | DATE | NOT NULL |
| `interval_hours` | SMALLINT | NOT NULL, CHECK IN (6,12,24,48) |
| `is_active` | BOOLEAN | NOT NULL, DEFAULT true |
| `min_price_seen` | NUMERIC(10,2) | NULLABLE (lowest price ever recorded) |
| `last_successful_run_at` | TIMESTAMPTZ | NULLABLE |
| `next_run_at` | TIMESTAMPTZ | NOT NULL |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() |
| `updated_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() |

**Unique constraint**: `(user_id, property_id, check_in, check_out)`.

**Rules**:
- Per-user limit: max 20 active rows where `user_id = X AND is_active = true`.
- Auto-deactivate: worker sets `is_active = false` when `check_in <= today()` (FR-014).
- `min_price_seen` uses "lowest ever recorded" baseline — same logic as TrackedSearch (clarification Q3).

---

## Entity: PriceSnapshot

An immutable historical record of a price observed for a property at a point in time.
Written on every successful background cycle for TrackedProperty.

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | UUID | PK |
| `property_id` | UUID | FK → Property.id, NOT NULL |
| `user_id` | UUID | FK → User.id, NOT NULL |
| `check_in` | DATE | NOT NULL |
| `check_out` | DATE | NOT NULL |
| `price` | NUMERIC(10,2) | NOT NULL |
| `source` | VARCHAR(50) | NOT NULL ('property_worker'\|'search_worker') |
| `observed_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() |

**Rules**:
- Written ONLY on successful (non-discarded) scrape cycles.
- Used for time-series display but not as the canonical min-price (that lives on
  TrackedProperty.min_price_seen and TrackedSearchSeenProperty.min_price_seen).

---

## Entity: NotificationLog

An immutable record of every alert dispatched to the user, regardless of channel.

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | UUID | PK |
| `user_id` | UUID | FK → User.id, NOT NULL |
| `type` | VARCHAR(30) | NOT NULL: 'new_listing'\|'price_drop' |
| `channel` | VARCHAR(20) | NOT NULL: 'telegram' (extensible) |
| `property_id` | UUID | FK → Property.id, NOT NULL |
| `tracked_search_id` | UUID | FK → TrackedSearch.id, NULLABLE |
| `tracked_property_id` | UUID | FK → TrackedProperty.id, NULLABLE |
| `price_before` | NUMERIC(10,2) | NULLABLE |
| `price_after` | NUMERIC(10,2) | NOT NULL |
| `property_url` | TEXT | NOT NULL (snapshot; URL may change) |
| `sent_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() |
| `delivery_status` | VARCHAR(20) | NOT NULL: 'sent'\|'failed' |

**Rules**:
- All queries MUST be scoped to `user_id` (FR-015).
- Records are immutable — never updated or deleted.

---

## Entity: TelegramLinkCode

Short-lived one-time code used in the Telegram account linking flow. Stored in Redis, not
PostgreSQL, because it is ephemeral (15-minute TTL).

**Redis key**: `telegram_link:<code>` → `user_id` (UUID string)
**TTL**: 900 seconds (15 minutes)

**Rules**:
- Code MUST be deleted from Redis immediately after first use.
- A second `/start <code>` with the same code MUST fail silently (key already gone).

---

## State Transitions

### TrackedSearch / TrackedProperty lifecycle

```
created (is_active=true)
  → active: next_run_at reached → worker picks up → runs cycle
    → cycle ok: update baseline, set next_run_at, emit notifications if any
    → cycle discarded: no writes, no notifications, next_run_at unchanged (retry next tick)
  → untracked: user calls untrack → is_active=false
  → auto-expired (TrackedProperty only): check_in <= today → is_active=false
```

### Search lifecycle

```
pending → running → partial (first results in) → complete | failed
```

---

## Index Notes

- `TrackedSearch`: index on `(is_active, next_run_at)` for worker polling.
- `TrackedProperty`: index on `(is_active, next_run_at)` for worker polling.
- `TrackedProperty`: index on `(user_id, check_in)` for auto-deactivation sweep.
- `NotificationLog`: index on `(user_id, sent_at DESC)` for history view.
- `TrackedSearchSeenProperty`: index on `tracked_search_id` for fast diff lookup.
- `Property`: unique index on `(provider, provider_property_id)` for upsert.
