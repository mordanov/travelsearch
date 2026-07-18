# TravelSearch

Unified accommodation search across Booking.com and Airbnb with price-drop tracking and Telegram alerts — for personal or family use.

## What it does

- **Search**: Run a single query that hits both Booking.com and Airbnb simultaneously. Results are merged, deduplicated, and shown in a sortable/filterable table. Export to CSV.
- **Track a search**: Save any search to re-run automatically (every 6, 12, 24, or 48 hours). Get a Telegram alert when a new listing appears or when a price drops below its lowest ever recorded value.
- **Track a property**: Send `/follow <url>` to the Telegram bot with a Booking or Airbnb link. The bot extracts the dates from the URL and monitors that exact property. Tracking stops automatically after check-in.
- **Notification history**: All alerts are logged in-app regardless of whether Telegram is linked.

## Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.13, FastAPI (async), SQLAlchemy 2.x + Alembic, arq + Redis |
| Scraping | Playwright async, proxied per-job browser contexts |
| Frontend | React 19, TypeScript strict, Vite, React Query, React Router |
| Auth | Argon2id passwords, HS256 JWT (in-memory access token + HttpOnly refresh cookie) |
| Notifications | Telegram Bot API via webhook |
| Infrastructure | PostgreSQL, Redis, Nginx + Let's Encrypt, Docker Compose |

## Quick start

**Prerequisites**: Docker + Docker Compose v2.

```bash
cp .env.example .env
# Fill in the required values in .env (see below)
docker compose up --build
```

Open `http://localhost` — login with the account you create via:

```bash
docker compose run --rm backend python -m app.cli create-user \
  --email you@example.com --password yourpassword
```

### Required environment variables

| Variable | Description |
|---|---|
| `DATABASE_URL` | PostgreSQL async URL (`postgresql+asyncpg://...`) |
| `REDIS_URL` | Redis URL (`redis://redis:6379/0`) |
| `JWT_SECRET` | Random string, at least 32 characters |
| `TELEGRAM_BOT_TOKEN` | From [@BotFather](https://t.me/BotFather) |
| `TELEGRAM_WEBHOOK_SECRET` | Any random string — used to validate incoming webhook calls |
| `PROXY_PROVIDER_HOST` | Proxy host for scraping (required to avoid blocks) |
| `PROXY_PROVIDER_USER` | Proxy username |
| `PROXY_PROVIDER_PASS` | Proxy password |
| `CORS_ORIGINS` | Comma-separated allowed origins (e.g. `http://localhost:3000`) |

See `.env.example` for all variables with descriptions.

### Register the Telegram webhook (production)

```bash
curl "https://api.telegram.org/bot<TOKEN>/setWebhook" \
  -d "url=https://<your-domain>/api/v1/telegram/webhook" \
  -d "secret_token=<TELEGRAM_WEBHOOK_SECRET>"
```

## Running tests

```bash
# All backend tests (unit + integration — no live providers, no live Telegram)
docker compose run --rm backend pytest tests/

# Contract tests only (recorded fixtures)
docker compose run --rm backend pytest tests/contract/

# Frontend
docker compose run --rm frontend npm test
```

## Project structure

```
backend/
  app/
    api/v1/routes/     REST endpoints
    services/          Business logic (TrackingService, SearchService, …)
    providers/         Booking + Airbnb scrapers (Provider ABC)
    notifiers/         Telegram notifier (Notifier ABC)
    workers/           arq background jobs
    models/            SQLAlchemy models
    repositories/      DB query layer
    schemas/           Pydantic v2 request/response schemas
    core/              Config, security, database, Redis, logging
  alembic/             Migrations
frontend/
  src/
    pages/             Route-level page components
    components/        Shared UI components
    hooks/             React Query hooks + auth state
    api/               Axios client + typed API wrappers
agents/                Claude Code agent skill files (for run-agents.sh)
specs/                 Feature specifications and planning documents
docker/                Dockerfiles and Nginx config
```

## Multi-agent development (optional)

This project ships with `run-agents.sh`, which launches 10 specialized Claude Code agents (product manager, software architect, security architect, frontend developer, backend developer, designer, devops, code reviewer, autotester, project administrator) in separate terminals, coordinated via [brainstorm-mcp](https://github.com/BMO-tech-corp/brainstorm-mcp).

```bash
# Prerequisites: Claude Code CLI + brainstorm-mcp installed
bash run-agents.sh
```

Each agent reads its role and responsibilities from `agents/<role>.md`.

## Accounts

There is no self-registration. Accounts are created by the administrator via the CLI:

```bash
docker compose run --rm backend python -m app.cli create-user \
  --email user@example.com --password <password>
```

## Tracking limits

- Max **10 active tracked searches** per user
- Max **20 active tracked properties** per user
- Tracking intervals: 6h / 12h / 24h / 48h
- A tracked property deactivates automatically when its check-in date passes

## Security notes

- Proxy credentials are never logged or returned in responses
- The Telegram webhook validates `X-Telegram-Bot-Api-Secret-Token` on every request
- All tracking and notification queries are scoped to the authenticated user — client-supplied user IDs are never trusted
- The backend is not directly reachable from the internet; Nginx is the sole entry point
- Refresh tokens are revocable via `POST /auth/logout`
