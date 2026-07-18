# Implementation Plan: Accommodation Search MVP

**Branch**: `001-accommodation-search-mvp` | **Date**: 2026-07-19 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/001-accommodation-search-mvp/spec.md`

## Summary

Build the TravelSearch MVP: a multi-user web application that aggregates accommodation
listings from Booking and Airbnb via Playwright scraping, tracks saved searches and
specific properties for price drops, and delivers alerts through a Telegram bot. The stack
is fully locked by the constitution: Python 3.13 + FastAPI (async), React 19 + TypeScript
strict, PostgreSQL + SQLAlchemy 2.x + Alembic, Redis + arq, Playwright async, Nginx + TLS,
deployed via Docker Compose.

## Technical Context

**Language/Version**: Python 3.13 (backend + scraper), TypeScript 5.x / React 19 (frontend)
**Primary Dependencies**: FastAPI, SQLAlchemy 2.x, Alembic, Pydantic v2, Playwright (async),
arq, structlog, Argon2id, python-jose (JWT), Axios, React Query, Vite
**Storage**: PostgreSQL (primary), Redis (job queue + arq state)
**Testing**: pytest + pytest-asyncio (backend), Vitest (frontend)
**Target Platform**: Linux VPS (Docker Compose), local dev via Docker Compose
**Project Type**: Web service (REST API + Telegram bot + React SPA)
**Performance Goals**: Search completes ≤2 min per provider, ≤3 min total (SC-001)
**Constraints**: No live provider calls in CI; all secrets via `.env`; no blocking I/O in
async contexts; Telegram webhook must be HTTPS-reachable
**Scale/Scope**: Personal/small-team use; per-user limits: 10 TrackedSearches, 20 TrackedProperties

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

- [x] **I. Provider & Notifier Isolation** — All scraping goes through `Provider` interface
  only. All notifications go through `Notifier` interface only. No backend code calls
  `BookingProvider` or `AirbnbProvider` directly. No API route calls Telegram directly.
- [x] **II. Single Authority** — `TrackingService` is the sole owner of
  create/remove TrackedSearch, create/remove TrackedProperty, dedup, and interval
  validation. REST routes and Telegram handler both call `TrackingService`; neither
  re-implements logic.
- [x] **III. Test Coverage** — Plan includes: unit tests (TrackingService, diff logic),
  integration tests (API endpoints + Telegram webhook handler with mocked Telegram API),
  provider contract tests (BookingProvider + AirbnbProvider against recorded fixtures,
  never live), notifier contract tests (TelegramNotifier with mocked Telegram API).
- [x] **IV. Async-Native Stack** — FastAPI async, Playwright async, arq workers, Redis only.
  No blocking I/O in async paths. No Celery, RabbitMQ, or sync Playwright calls.
- [x] **V. Safe Scraping** — FR-013 + background worker design enforce discard of
  blocked/CAPTCHA'd/incomplete cycles. Workers never diff a discarded cycle. Trip search
  (FlightProvider pipeline) is out of scope for this MVP — no violation.
- [x] **VI. Strict Typing** — mypy strict + Ruff on all backend/scraper code; TypeScript
  strict on frontend; all secrets via `.env`; SQLAlchemy 2.x + Alembic; Pydantic v2.
- [x] **VII. Docker-First** — SC-006 requires `docker compose up`. Docker Compose covers
  frontend, backend, worker, scheduler, db, redis, nginx. Nginx terminates TLS.

All gates pass. No complexity violations.

## Project Structure

### Documentation (this feature)

```text
specs/001-accommodation-search-mvp/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   ├── api.md           # REST API contract
│   └── provider-interface.md  # Provider/Notifier typed interfaces
└── tasks.md             # Phase 2 output (/speckit-tasks — not created here)
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── api/
│   │   └── v1/
│   │       ├── routes/
│   │       │   ├── auth.py
│   │       │   ├── search.py
│   │       │   ├── tracked_search.py
│   │       │   ├── tracked_property.py
│   │       │   ├── notifications.py
│   │       │   └── telegram.py
│   │       └── deps.py
│   ├── services/
│   │   ├── tracking_service.py    # Single authority for all tracking logic
│   │   ├── search_service.py
│   │   ├── auth_service.py
│   │   └── notification_service.py
│   ├── providers/
│   │   ├── base.py                # Provider ABC + FlightProvider ABC
│   │   ├── booking.py             # BookingProvider implements Provider
│   │   └── airbnb.py              # AirbnbProvider implements Provider
│   ├── notifiers/
│   │   ├── base.py                # Notifier ABC
│   │   └── telegram.py            # TelegramNotifier implements Notifier
│   ├── workers/
│   │   ├── search_worker.py       # arq job: re-run TrackedSearch
│   │   └── property_worker.py     # arq job: re-check TrackedProperty
│   ├── models/                    # SQLAlchemy 2.x ORM models
│   ├── repositories/              # DB access (one file per aggregate)
│   ├── schemas/                   # Pydantic v2 request/response schemas
│   └── core/
│       ├── config.py              # pydantic-settings from .env
│       └── security.py            # JWT (python-jose), Argon2id
├── alembic/
│   └── versions/
├── tests/
│   ├── unit/                      # TrackingService, diff logic
│   ├── integration/               # API endpoints, Telegram webhook
│   └── contract/                  # Provider + Notifier contract tests
└── pyproject.toml

frontend/
├── src/
│   ├── pages/
│   │   ├── LoginPage.tsx
│   │   ├── SearchPage.tsx
│   │   ├── SearchProgressPage.tsx
│   │   ├── SearchResultsPage.tsx
│   │   ├── PropertyDetailPage.tsx
│   │   ├── TrackedDashboardPage.tsx
│   │   ├── NotificationHistoryPage.tsx
│   │   └── TelegramLinkPage.tsx
│   ├── components/
│   ├── hooks/
│   ├── api/                       # Axios instance + React Query hooks
│   └── types/
├── tests/
└── package.json

docker/
├── backend/Dockerfile
├── frontend/Dockerfile
└── nginx/
    └── nginx.conf

docker-compose.yml
.env.example
```

**Structure Decision**: Web application layout (backend + frontend + docker). Backend is a
Python package rooted at `backend/app/`. Frontend is a Vite + React SPA at `frontend/`.
Infrastructure lives in `docker/` with a root-level `docker-compose.yml`.

## Complexity Tracking

*No Constitution Check violations — table not required.*
