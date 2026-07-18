# ADR 001: Async Stack — FastAPI + arq

## Status
Accepted

## Context

TravelSearch's backend must handle two fundamentally async workloads simultaneously:

1. **Interactive search requests** — each search spawns concurrent Playwright browser
   sessions against two providers and must complete within 3 minutes (SC-001). These
   sessions are CPU-light but I/O-heavy (network + DOM parsing).

2. **Background scheduling** — tracked searches and tracked properties re-run at
   user-configured intervals (6h/12h/24h/48h). These jobs must not block the HTTP API.

The Python ecosystem offers two async web frameworks (FastAPI, Starlette) and several
background job options (Celery+RabbitMQ, arq, APScheduler, rq). The choice affects
the entire backend threading model, library compatibility, and operational complexity.

## Decision Drivers

- Playwright's async API requires an event loop — sync frameworks introduce
  `run_until_complete` wrappers that risk blocking the event loop.
- Constitution mandates "async-native" — no blocking I/O in async paths.
- Personal/family scale: a single VPS, no need for distributed multi-worker queues.
- Redis is already required (JWT revocation, search progress, Telegram link codes) —
  reusing it as the job broker eliminates a separate message broker.
- Team capability: Python 3.13, FastAPI, and arq are the mandated stack.

## Options Considered

### Option A — FastAPI + arq (chosen)

- **Pros**: Both are fully async-native; Playwright async fits naturally; arq uses
  Redis natively (already a required dependency); minimal operational footprint (no
  separate broker process); supports `cron` scheduling built-in; integrates cleanly
  with SQLAlchemy 2.x async sessions.
- **Cons**: arq's cron granularity is 1-minute minimum; not suitable for sub-minute
  jobs (not a requirement here). arq is less battle-tested than Celery at very high
  throughput (not a concern at personal scale).
- **Risks**: If Redis becomes unavailable, background jobs stop silently. Mitigation:
  health check on Redis in Docker Compose; structured log on worker startup failure.

### Option B — FastAPI + Celery + RabbitMQ

- **Pros**: Celery is mature with large ecosystem; RabbitMQ has durable queues.
- **Cons**: RabbitMQ is an additional stateful service (RAM, config, ops); Celery's
  default workers are sync — async Playwright calls require Celery's `asyncio` pool
  (experimental), or running sync wrappers. Operational complexity outweighs benefit
  at this scale.
- **Risks**: Extra broker increases blast radius of a single service failure.

### Option C — FastAPI + APScheduler

- **Pros**: In-process scheduling, no Redis dependency for jobs.
- **Cons**: APScheduler stores state in memory — a container restart loses the
  schedule. Persistent stores (DB-backed) add complexity. No job queue semantics
  (retry, backoff, visibility). Does not integrate as cleanly with arq's per-job
  Redis-backed state.
- **Risks**: Job state loss on pod restart; harder to test in isolation.

## Decision

**FastAPI + arq**, with Redis shared between JWT revocation, search progress, Telegram
link codes, and the arq job queue. The `scheduler` Docker Compose service runs arq's
built-in cron to enqueue `rerun_tracked_search` and `recheck_tracked_property` every
5 minutes. Workers fetch `next_run_at`-overdue rows and process them.

## Consequences

- **Positive**: Single event loop per process; Playwright, SQLAlchemy async, and httpx
  all compose correctly; Redis is the only stateful dependency outside PostgreSQL.
- **Negative**: Background jobs are lost if Redis is down during enqueue. Mitigation:
  workers are idempotent — they re-read `next_run_at` from DB on each tick, so a
  missed Redis enqueue is caught on the next 5-minute poll.
- **Operational**: `docker compose` runs `backend` (API), `worker` (arq worker),
  and `scheduler` (arq cron) as separate services from the same image.

## Validation and Fitness Functions

- `pytest --asyncio-mode=auto` confirms all service layer tests run without
  `run_until_complete` or sync Playwright calls.
- `mypy --strict` confirms no `asyncio.run()` inside async functions.
- Integration test: arq job enqueued in test environment completes without event-loop
  blocking warnings.

## Reversal or Migration Strategy

If arq proves insufficient (e.g., job volume grows): replace `worker/` and
`scheduler/` services with Celery+Redis without touching the `Provider`, `Notifier`,
or `TrackingService` interfaces. The job boundary is `rerun_tracked_search()` and
`recheck_tracked_property()` — callers above this boundary are unchanged.
