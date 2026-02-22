"""Background scheduler for periodic tasks."""

from __future__ import annotations

import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from core.idle import apply_config_suggestions
from core import logging as timeline_log

logger = logging.getLogger("camguard.scheduler")

scheduler = AsyncIOScheduler()


def start_scheduler():
    scheduler.add_job(
        _snowflake_flush,
        "interval",
        seconds=10,
        id="snowflake_flush",
        replace_existing=True,
    )

    scheduler.add_job(
        _config_optimization,
        "interval",
        minutes=5,
        id="config_optimization",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("Background scheduler started")


async def _snowflake_flush():
    try:
        await timeline_log.flush_to_snowflake()
    except Exception as e:
        logger.error("Snowflake flush job error: %s", e)


async def _config_optimization():
    try:
        await apply_config_suggestions()
    except Exception as e:
        logger.error("Config optimization job error: %s", e)


def stop_scheduler():
    scheduler.shutdown(wait=False)
