# Contributing

## Getting started

1. Clone the repository and create a `.env` from `.env.example`
2. Start the stack: `docker compose up --build`
3. Create a user account: `docker compose run --rm backend python -m app.cli create-user --email dev@example.com --password dev`
4. Run tests to confirm a working baseline: `docker compose run --rm backend pytest tests/`

## Branch naming

Feature branches follow the spec directory naming convention:

```
<number>-<short-description>
```

Example: `001-accommodation-search-mvp`

## Development workflow

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
# Requires local PostgreSQL + Redis, or set DATABASE_URL/REDIS_URL to point at Docker services
uvicorn app.main:app --reload
```

Run type checks and linting before committing:

```bash
mypy --strict app/
ruff check app/
ruff format app/
```

### Frontend

```bash
cd frontend
npm install
npm run dev      # dev server at http://localhost:3000
npm test         # Vitest
tsc --noEmit     # type check
```

### Database migrations

Create a migration after changing SQLAlchemy models:

```bash
docker compose run --rm backend alembic revision --autogenerate -m "describe change"
# Review the generated file in alembic/versions/ before committing
docker compose run --rm backend alembic upgrade head
```

Always verify both directions:

```bash
docker compose run --rm backend alembic upgrade head
docker compose run --rm backend alembic downgrade -1
docker compose run --rm backend alembic upgrade head
```

## Architecture constraints

These rules are non-negotiable. PRs that violate them will not be merged.

### Provider isolation

Backend code must only call `Provider` and `Notifier` ABCs — never import `BookingProvider`, `AirbnbProvider`, or `TelegramNotifier` directly outside their respective packages (`app/providers/`, `app/notifiers/`).

### Single tracking authority

`TrackingService` is the sole owner of all tracking logic. The REST API and the Telegram bot both delegate to it. Neither may contain tracking business logic directly.

### Safe-discard invariant

A scrape cycle that returns `ScrapeStatus.BLOCKED`, `ScrapeStatus.CAPTCHA`, or `ScrapeStatus.INCOMPLETE` **must be discarded entirely** — no DB writes, no baseline updates, no notifications. Workers check `result.status == ScrapeStatus.OK` before any diff or write. This is enforced by a release-gate test; do not remove or weaken it.

### Per-user data isolation

All queries for `TrackedSearch`, `TrackedProperty`, `NotificationLog`, and `PriceSnapshot` must be scoped to the authenticated user. Client-supplied user IDs must never be trusted.

### Secrets discipline

- All secrets live in `.env` only — never in source files, never committed
- Proxy credentials must never appear in logs or HTTP responses
- `hashed_password` must never appear in any Pydantic response schema

## Tests

### What to test and how

- **Unit tests**: Use mocked DB fixtures. Do not hit a real database.
- **Integration tests**: Use the async test DB fixture in `tests/conftest.py` (rolls back after each test). Mock `TelegramNotifier.send()` — do not call the real Telegram API.
- **Contract tests**: Use recorded HTML/JSON fixtures in `tests/contract/fixtures/`. Never make live requests to Booking.com or Airbnb in CI.
- **Safe-discard invariant test**: Lives in `tests/integration/` and is tagged as a release gate. Do not skip it.

Run the full suite:

```bash
docker compose run --rm backend pytest tests/ --tb=short
```

Run with coverage:

```bash
docker compose run --rm backend pytest tests/ --cov=app --cov-report=term-missing
```

## Adding a new provider

1. Create `backend/app/providers/<name>.py` implementing the `Provider` ABC from `app/providers/base.py`
2. All scraping failures must be encoded in `ScrapeStatus` — the method must not raise
3. Add recorded fixture files under `tests/contract/fixtures/<name>/`
4. Add a contract test in `tests/contract/test_<name>_provider.py` using those fixtures
5. Register the provider in `SearchService` via the `Provider` interface — no direct imports elsewhere

## Adding a new notifier

1. Create `backend/app/notifiers/<name>.py` implementing the `Notifier` ABC from `app/notifiers/base.py`
2. `send()` must return `False` on failure — it must never raise
3. Register it in the worker via the `Notifier` interface

## Commit style

```
type: short summary in imperative mood

type is one of: feat, fix, refactor, test, docs, chore
```

Examples:

```
feat: add TrackedProperty auto-deactivation on check-in date
fix: discard INCOMPLETE scrape cycles before diff
test: add release-gate test for safe-discard invariant
```

One logical change per commit. Migrations get their own commit.

## Pull requests

- Title: under 70 characters, imperative mood
- Body: what changed and why (not a list of files touched)
- All tests must pass
- `mypy --strict` and `tsc --noEmit` must pass with no new errors
- The safe-discard invariant test must pass
- No `hashed_password` in any response schema
- No new `any` types in TypeScript
- No wildcard `*` in CORS config

## Multi-agent development

`run-agents.sh` launches 10 Claude Code agents in separate terminals for collaborative implementation. Each agent reads its role from `agents/<role>.md`. The project-administrator agent must signal `pa-ready` before the rest of the team launches.

```bash
bash run-agents.sh [--project <project-name>]
```

Agent skill files live in `agents/`. Edit them to change an agent's responsibilities, project-specific context, or constraints.
