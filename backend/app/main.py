from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.routes import (
    auth,
    notifications,
    property,
    search,
    telegram,
    tracked_property,
    tracked_search,
)
from app.core.config import get_settings
from app.core.database import get_session_factory
from app.core.logging import configure_logging
from app.core.security import hash_password
from app.repositories import user_repository

configure_logging()

log = structlog.get_logger(__name__)


async def _seed_default_user() -> None:
    settings = get_settings()
    if not settings.default_user_email or not settings.default_user_password:
        return
    factory = get_session_factory()
    async with factory() as session:
        async with session.begin():
            existing = await user_repository.get_by_email(session, settings.default_user_email)
            if existing is None:
                await user_repository.create_user(
                    session,
                    email=settings.default_user_email,
                    hashed_password=hash_password(settings.default_user_password),
                )
                log.info("default_user_created", email=settings.default_user_email)
            else:
                existing.hashed_password = hash_password(settings.default_user_password)
                log.info("default_user_password_synced", email=settings.default_user_email)


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncGenerator[None]:
    await _seed_default_user()
    yield


settings = get_settings()

app = FastAPI(
    title="TravelSearch API",
    version="0.1.0",
    docs_url="/api/v1/docs",
    openapi_url="/api/v1/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "type": "https://tools.ietf.org/html/rfc7807",
            "title": "Validation Error",
            "status": 422,
            "detail": exc.errors(),
            "instance": str(request.url),
        },
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    import structlog

    log = structlog.get_logger(__name__)
    log.exception("unhandled_exception", path=str(request.url))
    return JSONResponse(
        status_code=500,
        content={
            "type": "https://tools.ietf.org/html/rfc7807",
            "title": "Internal Server Error",
            "status": 500,
            "detail": "An unexpected error occurred.",
            "instance": str(request.url),
        },
    )


API_PREFIX = "/api/v1"
app.include_router(auth.router, prefix=API_PREFIX)
app.include_router(search.router, prefix=API_PREFIX)
app.include_router(property.router, prefix=API_PREFIX)
app.include_router(tracked_search.router, prefix=API_PREFIX)
app.include_router(tracked_property.router, prefix=API_PREFIX)
app.include_router(notifications.router, prefix=API_PREFIX)
app.include_router(telegram.router, prefix=API_PREFIX)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
