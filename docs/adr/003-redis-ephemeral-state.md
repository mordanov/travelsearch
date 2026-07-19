# ADR 003: Redis for Ephemeral and Transient State

## Status
Accepted

## Context

TravelSearch requires several categories of short-lived state that do not warrant
durable PostgreSQL rows:

1. **Search progress** — real-time provider status during a live search (polling target
   for `GET /search/{id}/status`). Lifetime: minutes; lost on Redis restart without harm
   (search is already complete or will re-run).
2. **JWT refresh token revocation list** — tokens revoked on logout must be blocked for
   their remaining TTL (up to 30 days). PostgreSQL could store these but adds write
   pressure on every logout and every refresh token validation.
3. **Telegram link codes** — one-time codes with 15-minute TTL. Single read-and-delete
   semantics.
4. **arq job queue** — arq uses Redis natively as its job broker and state store.

The question is whether to use PostgreSQL for all of these (simpler operational stack)
or introduce Redis as a second stateful dependency.

## Decision Drivers

- arq is mandated by the constitution — Redis is a hard dependency for the job queue
  regardless of other choices.
- Telegram link codes require single-use semantics with atomic read-and-delete (Redis
  `GET` + `DEL` or `GETDEL`) — trivially safe in Redis; requires a transaction +
  `FOR UPDATE` in PostgreSQL.
- Search progress is write-heavy during scraping (multiple updates per second) and
  read-heavy during polling — a PostgreSQL row with frequent updates would generate
  excessive WAL/MVCC overhead.
- JWT revocation at-scale: Redis `SET key "" EX ttl` is O(1) with no table growth.

## Options Considered

### Option A — Redis for ephemeral state (chosen)

- **Pros**: TTL semantics are native; atomic `GETDEL` for link codes; O(1) revocation
  checks; arq already uses Redis; no schema migration needed for ephemeral data.
- **Cons**: Redis is a second stateful service to operate and back up.
- **Risks**: Redis data is lost on restart without persistence config. Mitigations:
  (a) all Redis data is ephemeral by design — loss is acceptable; (b) Docker Compose
  mounts a volume for Redis to survive container restarts; (c) health checks gate
  dependent services.

### Option B — PostgreSQL for all state

- **Pros**: Single stateful service; consistent backup/restore.
- **Cons**: arq still requires Redis — this option adds a PostgreSQL table while
  keeping Redis anyway. Telegram link-code single-use is clumsy without `FOR UPDATE`.
  Search progress as a polled PostgreSQL column is noisy WAL traffic.
- **Risks**: Larger schema; more table lock contention during search runs.

### Option C — SQLite for ephemeral state

- **Pros**: No additional service.
- **Cons**: No TTL support; concurrent async writers require careful locking; not
  compatible with arq.
- **Risks**: Does not solve arq dependency.

## Decision

**Redis** is used for: search progress keys (`search:{id}:status`), JWT revocation
set (`jwt:revoked:{jti}`), Telegram link codes (`telegram_link:{code}`), and arq
job queue. Redis is configured with volume-backed persistence in Docker Compose
(`appendonly yes` for AOF) but treated as recoverable — loss of ephemeral data
requires users to re-login (new tokens) and re-submit any in-flight search.

All Redis keys use prefixed namespacing to prevent collisions:
- `search:{uuid}:status` → JSON blob
- `jwt:revoked:{jti}` → `"1"` with EX = remaining token lifetime
- `telegram_link:{code}` → `user_id` (UUID string) with EX = 900
- arq keys use the `arq:` prefix (arq-native)

## Consequences

- **Positive**: Sub-millisecond revocation checks; no PostgreSQL contention during
  search progress polling; single-use link codes are safe and atomic.
- **Negative**: Operators must monitor Redis memory. At personal scale (< 100 users),
  this is trivial.
- **Operational**: Redis health check (`redis-cli ping`) added to Docker Compose
  `healthcheck`. Backend and worker services have `depends_on: redis: condition: healthy`.

## Validation and Fitness Functions

- `tests/conftest.py` `redis_mock` fixture confirms all Redis operations use the
  namespaced key format.
- Integration test: `/start <code>` used twice — second use returns "expired" (key gone).
- Integration test: logout → revoked token → `POST /auth/refresh` returns 401.

## Reversal or Migration Strategy

If Redis is removed: migrate revocation list to a PostgreSQL `revoked_tokens` table
with a cleanup job; migrate link codes to a `telegram_link_codes` table with a
short-lived TTL enforced by a cleanup cron; replace arq with APScheduler (DB-backed).
Each of these is an independent change — no provider or notifier code is affected.
