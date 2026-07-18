from arq import cron
from arq.connections import RedisSettings

from app.core.config import get_settings
from app.workers.property_worker import recheck_tracked_property
from app.workers.search_worker import rerun_tracked_search


def _redis_settings() -> RedisSettings:
    settings = get_settings()
    return RedisSettings.from_dsn(settings.redis_url)


async def startup(ctx: dict) -> None:
    # Constitution I: provider registry built once at worker startup, injected via ctx
    from app.providers.booking import BookingProvider
    from app.providers.airbnb import AirbnbProvider
    ctx["providers"] = {"booking": BookingProvider(), "airbnb": AirbnbProvider()}


class WorkerSettings:
    on_startup = startup
    functions = [rerun_tracked_search, recheck_tracked_property]
    cron_jobs = [
        cron(rerun_tracked_search, minute={0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55}),
        cron(recheck_tracked_property, minute={0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55}),
    ]
    redis_settings = _redis_settings()
    max_jobs = 10
    job_timeout = 300
