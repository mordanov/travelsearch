# Quickstart: Accommodation Search MVP

**Branch**: `001-accommodation-search-mvp` | **Date**: 2026-07-19

## Prerequisites

- Docker + Docker Compose v2
- `.env` file at project root (copy from `.env.example`)

## Environment Variables

```bash
cp .env.example .env
# Edit .env and fill in:
DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/travelsearch
REDIS_URL=redis://redis:6379/0
JWT_SECRET=<at-least-32-random-chars>
JWT_ALGORITHM=HS256
TELEGRAM_BOT_TOKEN=<from @BotFather>
TELEGRAM_WEBHOOK_SECRET=<random-string-for-header-validation>
PROXY_PROVIDER_HOST=<proxy-host>
PROXY_PROVIDER_USER=<proxy-user>
PROXY_PROVIDER_PASS=<proxy-pass>
CORS_ORIGINS=http://localhost:3000
```

## Start the full stack

```bash
docker compose up --build
```

Services started:
- `frontend` → http://localhost:3000
- `backend` → http://localhost:8000 (via Nginx: http://localhost/api/)
- `worker` — arq property + search background jobs
- `scheduler` — arq cron scheduler
- `db` — PostgreSQL
- `redis` — Redis
- `nginx` — reverse proxy (port 80 / 443 in production)

Alembic migrations run automatically on `backend` container start.

## Run tests

```bash
# Backend — unit + integration (no live providers)
docker compose run --rm backend pytest tests/

# Backend — contract tests only
docker compose run --rm backend pytest tests/contract/

# Frontend
docker compose run --rm frontend npm test
```

## Create a user account

```bash
docker compose run --rm backend python -m app.cli create-user \
  --email admin@example.com --password <password>
```

## Register Telegram webhook (production / VPS)

```bash
curl "https://api.telegram.org/bot<TOKEN>/setWebhook" \
  -d "url=https://<your-domain>/api/v1/telegram/webhook" \
  -d "secret_token=<TELEGRAM_WEBHOOK_SECRET>"
```

## Development without Docker

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
# Requires local PostgreSQL + Redis, or set DATABASE_URL/REDIS_URL to Docker services
uvicorn app.main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```
