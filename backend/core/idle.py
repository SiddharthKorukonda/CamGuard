"""Idle detection and self-optimization config application."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from store.db import async_session
from store.models import Camera, Incident, ConfigUpdate
from integrations import snowflake_client
from core import logging as timeline_log

logger = logging.getLogger("camguard.idle")

IDLE_MINUTES = 10


async def is_camera_idle(camera_id: str) -> bool:
    """A camera is idle when: no person present, no active incident, low risk_score."""
    async with async_session() as db:
        cam_result = await db.execute(select(Camera).where(Camera.id == camera_id))
        camera = cam_result.scalar_one_or_none()
        if not camera:
            return False

        if camera.risk_score > 0.3:
            return False

        inc_result = await db.execute(
            select(Incident).where(
                Incident.camera_id == camera_id,
                Incident.status == "ACTIVE",
            )
        )
        if inc_result.scalar_one_or_none():
            return False

    return True


async def apply_config_suggestions():
    """Read config suggestions from Snowflake and apply during idle windows."""
    suggestions = snowflake_client.read_config_suggestions(limit=20)
    if not suggestions:
        return

    for suggestion in suggestions:
        camera_id = suggestion.get("camera_id", "")
        if not camera_id:
            continue

        idle = await is_camera_idle(camera_id)
        if not idle:
            logger.info("Camera %s not idle – skipping config suggestion %s", camera_id, suggestion.get("id"))
            continue

        config_json = suggestion.get("config_json", {})
        if not config_json:
            continue

        allowed_keys = {
            "motion_spike_threshold", "stillness_threshold",
            "risk_threshold_low", "risk_threshold_high",
            "escalation_delay_s",
        }
        filtered = {k: v for k, v in config_json.items() if k in allowed_keys}
        if not filtered:
            continue

        try:
            async with async_session() as db:
                cam_result = await db.execute(select(Camera).where(Camera.id == camera_id))
                camera = cam_result.scalar_one_or_none()
                if not camera:
                    continue

                old_config = dict(camera.config or {})
                new_config = {**old_config, **filtered}
                camera.config = new_config

                update = ConfigUpdate(
                    camera_id=camera_id,
                    reason=suggestion.get("reason", "Snowflake optimization"),
                    confidence=suggestion.get("confidence", 0.0),
                    config_json=filtered,
                    applied=True,
                )
                db.add(update)
                await db.commit()

            now = datetime.now(timezone.utc)
            applied_id = str(uuid.uuid4())
            snowflake_client.write_config_applied(
                applied_id=applied_id,
                camera_id=camera_id,
                reason=suggestion.get("reason", ""),
                confidence=suggestion.get("confidence", 0.0),
                config_json=filtered,
                applied=True,
                ts=now,
            )

            await timeline_log.log_event(
                incident_id="system",
                camera_id=camera_id,
                kind="CONFIG_SUGGESTION_APPLIED",
                payload={"config": filtered, "reason": suggestion.get("reason", "")},
            )

            logger.info("Applied config suggestion to camera %s: %s", camera_id, filtered)

        except Exception as e:
            logger.error("Config application error for camera %s: %s", camera_id, e)
