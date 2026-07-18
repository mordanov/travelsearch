<!--
SYNC IMPACT REPORT
==================
Version change: [TEMPLATE] → 1.0.0
Ratification: Initial adoption from project constitution.md

Modified principles:
  All sections: Template placeholders → concrete project content (initial fill)

Added sections:
  - I. Provider & Notifier Isolation
  - II. Single Authority for Business Logic
  - III. Test Coverage (NON-NEGOTIABLE)
  - IV. Async-Native Stack
  - V. Safe Scraping & Graceful Degradation
  - VI. Strict Typing & Code Quality
  - VII. Docker-First Deployment
  - Technology Stack
  - Security & Multi-User
  - Governance

Templates requiring updates:
  ✅ .specify/memory/constitution.md — written now
  ✅ .specify/templates/plan-template.md — Constitution Check gates reference real principles
  ⚠ .specify/templates/spec-template.md — no constitution-specific changes required
  ⚠ .specify/templates/tasks-template.md — no constitution-specific changes required
  ⚠ .specify/templates/commands/ — directory does not exist; no command files to update

Deferred items:
  - RATIFICATION_DATE: set to today (2026-07-18); original project start date unknown
-->

# TravelSearch Constitution

## Core Principles

### I. Provider & Notifier Isolation

All accommodation providers MUST implement the `Provider` interface (`search`, `details`,
`parse_url`, `normalize`). All flight providers MUST implement `FlightProvider` (`explore`,
`search`). All notification channels MUST implement the `Notifier` interface (`send`).

The backend MUST NOT communicate directly with any provider or notifier implementation —
only through the typed interface. Each provider is independently replaceable and solely
responsible for its own anti-bot handling (proxy rotation, retry/backoff, fingerprint
randomization, CAPTCHA detection) behind that interface.

**Rationale**: Prevents scraping logic and notification logic from leaking into the backend.
New providers or channels can be added or swapped without touching business logic.

### II. Single Authority for Business Logic

The Tracking Service MUST be the sole owner of all tracking logic: creating/removing
`TrackedSearch`, creating/removing `TrackedProperty`, dedup checks, and interval validation.
Both the REST API and the Telegram command handler (`/follow`, `/unfollow`, `/list`) MUST
delegate to this same service. Command handling MUST NOT re-implement business logic.

**Rationale**: Divergence between the web UI and the bot is a class of bug that surfaces late
and is hard to test. A single authoritative service eliminates it structurally.

### III. Test Coverage (NON-NEGOTIABLE)

Every feature MUST include:
- Unit tests for business logic, including the Tracking Service and diffing logic.
- Integration tests for API endpoints and the Telegram webhook handler (mocked Telegram API).
- Provider contract tests run against recorded/mocked fixtures — NEVER against live
  Booking, Airbnb, Google Flights, or Skyscanner in CI.
- Notifier contract tests (mocked Telegram API).

Tests are part of the Definition of Done. A feature without its tests is not done.

**Rationale**: Provider scraping and Telegram integration cannot be regression-tested against
live services safely or repeatably; fixture-based contract tests are the only viable gate.

### IV. Async-Native Stack

The entire backend and scraper stack MUST be async-native: Python 3.13 with FastAPI (async),
Playwright (async) for scraping, and arq workers for background jobs. Blocking I/O MUST NOT
appear in async contexts. Redis + arq is the only approved background job mechanism — no
separate brokers (RabbitMQ, Celery with non-async backends).

**Rationale**: Playwright's async API fits FastAPI's event loop directly. Introducing blocking
I/O or a synchronous broker would require a separate thread/process boundary, increasing
complexity without benefit.

### V. Safe Scraping & Graceful Degradation

A scrape cycle that is blocked, CAPTCHA'd, or returns a suspiciously incomplete result set
MUST be discarded entirely — it MUST NOT be diffed, compared, or allowed to trigger
notifications. "Incomplete" is provider-defined but MUST be detected and logged.

Trip search MUST follow the two-stage pipeline: `FlightProvider.explore()` runs first and
returns the top N cheapest candidates (N ≤ 20). Accommodation scraping runs ONLY against
that shortlist. A failed flight-explore cycle MUST abort the entire trip-search cycle.

Providers MUST throttle and degrade gracefully (skip, log, continue) rather than retry
aggressively into a block.

**Rationale**: A false "new listing" or false "price restored" notification erodes user trust
immediately and permanently. Correctness under adversarial scraping conditions is a
first-class constraint, not an edge case.

### VI. Strict Typing & Code Quality

- Python: mypy in strict mode, Ruff for linting and formatting. MANDATORY on all backend
  and scraper code.
- TypeScript: `strict: true` in tsconfig. MANDATORY on all frontend code.
- All configuration MUST flow through `.env` files (DB credentials, proxy credentials,
  Telegram bot token, JWT secret). Secrets MUST NOT be committed to the repository.
- SQLAlchemy 2.x + Alembic for all database access and migrations.
- Pydantic v2 for all data validation and serialization.

**Rationale**: Strict typing catches interface mismatches between provider implementations and
the backend before they become runtime errors. Configuration via `.env` is a hard security
requirement for a publicly deployed service.

### VII. Docker-First Deployment

The full stack (frontend, backend, worker, scheduler, PostgreSQL, Redis, Nginx) MUST be
runnable via a single `docker compose up`. Nginx MUST terminate TLS using Let's Encrypt and
act as the sole reverse proxy. The Telegram webhook endpoint MUST be reachable over HTTPS
(satisfied by the VPS + Nginx setup).

Each service is defined in `docker/` and composed in `docker-compose.yml` at the project
root. A feature is not deployable if it cannot be brought up with Docker Compose.

**Rationale**: Single-command deployment is the primary operational guarantee for a
self-hosted, personal-use service maintained by one person.

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Backend language | Python 3.13 |
| Backend framework | FastAPI (async) |
| Frontend | React 19 + TypeScript (strict) |
| Database | PostgreSQL |
| ORM / migrations | SQLAlchemy 2.x + Alembic |
| Validation | Pydantic v2 |
| Background jobs | Redis + arq |
| Scraping | Playwright (async) |
| Python quality | mypy (strict), Ruff |
| Testing | pytest |
| Reverse proxy | Nginx + Let's Encrypt |
| Deployment | Docker Compose on VPS |
| API style | REST only |

## Security & Multi-User

- No public self-registration. Accounts are provisioned manually by the admin via CLI
  script or admin-only endpoint.
- Authentication: email + password. Passwords MUST be hashed with Argon2id. Sessions MUST
  use JWT.
- Telegram linking: each user MAY link a personal Telegram chat via bot deep-link and
  one-time code. This enables both receiving alerts and issuing commands tied to their
  account.
- Rate limiting and brute-force protection MUST be applied to `POST /auth/login`.
- Secrets MUST only appear in `.env` files, never in source control.

## Governance

This constitution supersedes all other practices, preferences, or conventions documented
elsewhere. Any practice that contradicts a principle stated here is non-compliant.

**Amendment procedure**: Amendments MUST be documented with a version bump, a rationale, and
a migration plan for any affected artifacts. Backward-incompatible changes to principles
require a MAJOR version bump. New principles or material expansions require MINOR. Wording
and clarification changes require PATCH.

**Compliance review**: All plans, specs, and task lists MUST include a Constitution Check
gate verifying alignment with Principles I–VII before implementation begins. Plans that
introduce complexity violations MUST include a Complexity Tracking table justifying
each violation.

**Versioning policy**: `MAJOR.MINOR.PATCH` per semantic versioning rules defined above.

**Version**: 1.0.0 | **Ratified**: 2026-07-18 | **Last Amended**: 2026-07-18
