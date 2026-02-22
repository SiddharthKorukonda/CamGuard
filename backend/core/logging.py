"""Timeline event logging and Snowflake background writer."""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections import deque
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from store.db import async_session
from store.models import IncidentTimeline
from integrations import snowflake_client

logger = logging.getLogger("camguard.timeline")

_write_queue: deque[dict] = deque(maxlen=10000)
_ws_broadcast_fn = None


def set_ws_broadcast(fn):
    global _ws_broadcast_fn
    _ws_broadcast_fn = fn


async def log_event(
    incident_id: str,
    camera_id: str,
    kind: str,
    payload: dict | None = None,
    db: AsyncSession | None = None,
):
    """Log a timeline event to DB, queue for Snowflake, and broadcast via WS."""
    now = datetime.now(timezone.utc)
    event_id = str(uuid.uuid4())

    event = IncidentTimeline(
        id=event_id,
        incident_id=incident_id,
        camera_id=camera_id,
        kind=kind,
        ts=now,
        payload=payload,
    )

    if db:
        db.add(event)
        await db.commit()
    else:
        async with async_session() as session:
            session.add(event)
            await session.commit()

    _write_queue.append({
        "id": event_id,
        "incident_id": incident_id,
        "camera_id": camera_id,
        "kind": kind,
        "ts": now,
        "payload": payload,
    })

    if _ws_broadcast_fn:
        try:
            await _ws_broadcast_fn({
                "type": kind,
                "incident_id": incident_id,
                "camera_id": camera_id,
                "ts": now.isoformat(),
                "payload": payload,
            })
        except Exception as e:
            logger.error("WS broadcast error: %s", e)


async def flush_to_snowflake():
    """Drain the write queue and push to Snowflake."""
    while _write_queue:
        item = _write_queue.popleft()
        try:
            snowflake_client.write_timeline_event(
                event_id=item["id"],
                incident_id=item["incident_id"],
                camera_id=item["camera_id"],
                kind=item["kind"],
                ts=item["ts"],
                payload=item["payload"],
            )
        except Exception as e:
            logger.error("Snowflake flush error: %s", e)


async def get_timeline(incident_id: str) -> list[dict]:
    async with async_session() as session:
        result = await session.execute(
            select(IncidentTimeline)
            .where(IncidentTimeline.incident_id == incident_id)
            .order_by(IncidentTimeline.ts)
        )
        events = result.scalars().all()
        return [
            {
                "id": e.id,
                "incident_id": e.incident_id,
                "camera_id": e.camera_id,
                "kind": e.kind,
                "ts": e.ts.isoformat() if e.ts else "",
                "payload": e.payload,
            }
            for e in events
        ]
