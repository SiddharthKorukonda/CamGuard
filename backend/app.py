from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

env_path = Path(__file__).parent / ".env"
if env_path.exists():
    load_dotenv(env_path)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from store.db import init_db, async_session
from integrations import snowflake_client
from core.scheduler import start_scheduler, stop_scheduler
from core import logging as timeline_log
from api.websocket import broadcast

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger("camguard")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("CamGuard starting up...")
    await init_db()
    logger.info("Database initialized")

    await _clear_all_cameras()
    await _restore_onboarding_config()

    try:
        snowflake_client.ensure_tables()
        logger.info("Snowflake tables ensured")
    except Exception as e:
        logger.warning("Snowflake setup skipped: %s", e)

    timeline_log.set_ws_broadcast(broadcast)

    start_scheduler()
    logger.info("CamGuard ready")

    yield

    from core.vision import stop_all as stop_all_vision
    stop_all_vision()
    stop_scheduler()
    logger.info("CamGuard shut down")


app = FastAPI(
    title="CamGuard API",
    description="Agentic fall triage and response system for caregiver cameras",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

audio_dir = Path(__file__).parent / "audio_cache"
audio_dir.mkdir(exist_ok=True)
app.mount("/audio", StaticFiles(directory=str(audio_dir)), name="audio")

from api.cameras import router as cameras_router
from api.telemetry import router as telemetry_router
from api.incidents import router as incidents_router
from api.accessibility import router as accessibility_router
from api.websocket import router as ws_router
from api.twilio import router as twilio_router
from api.demo import router as demo_router
from api.agent import router as agent_router
from api.vision import router as vision_router

app.include_router(cameras_router)
app.include_router(telemetry_router)
app.include_router(incidents_router)
app.include_router(accessibility_router)
app.include_router(ws_router)
app.include_router(twilio_router)
app.include_router(demo_router)
app.include_router(agent_router)
app.include_router(vision_router)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "camguard",
        "gemini_model_fast": os.getenv("GEMINI_MODEL_FAST", "gemini-2.5-flash-lite"),
        "gemini_model_strong": os.getenv("GEMINI_MODEL_STRONG", "gemini-2.5-pro"),
        "snowflake_configured": bool(
            os.getenv("SNOWFLAKE_ACCOUNT") and not os.getenv("SNOWFLAKE_ACCOUNT", "").startswith("your-")
        ),
        "twilio_configured": bool(
            os.getenv("TWILIO_ACCOUNT_SID") and not os.getenv("TWILIO_ACCOUNT_SID", "").startswith("your-")
        ),
        "elevenlabs_configured": bool(
            os.getenv("ELEVENLABS_API_KEY") and not os.getenv("ELEVENLABS_API_KEY", "").startswith("your-")
        ),
    }


async def _clear_all_cameras():
    """Clear all cameras and incidents on startup so each run starts fresh.
    OnboardingConfig is preserved across restarts so contact info persists."""
    from sqlalchemy import delete
    from store.models import (
        Camera, NotificationPolicy, Incident, IncidentPlan,
        IncidentTimeline, ActionLog, ChatMessage, PerformanceMetric,
    )

    async with async_session() as db:
        await db.execute(delete(ActionLog))
        await db.execute(delete(IncidentTimeline))
        await db.execute(delete(IncidentPlan))
        await db.execute(delete(Incident))
        await db.execute(delete(NotificationPolicy))
        await db.execute(delete(Camera))
        await db.execute(delete(ChatMessage))
        await db.execute(delete(PerformanceMetric))
        await db.commit()
    logger.info("Cleared all cameras and incidents for fresh start")


async def _restore_onboarding_config():
    """Restore onboarding config from DB so contacts survive server restarts."""
    from sqlalchemy import select
    from store.models import OnboardingConfig
    from api.vision import set_monitoring_config

    async with async_session() as db:
        result = await db.execute(
            select(OnboardingConfig).order_by(OnboardingConfig.created_at.desc()).limit(1)
        )
        cfg = result.scalar_one_or_none()
        if cfg:
            set_monitoring_config(cfg.monitoring_type, cfg.primary_contact, cfg.backup_contact)
            logger.info(
                "Restored onboarding config: type=%s, primary=%s",
                cfg.monitoring_type, cfg.primary_contact or "(not set)",
            )
        else:
            logger.info("No onboarding config found – using defaults")
