from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks

from schemas import TelemetryPacket, TriggerKind
from core.planner import handle_prevention, handle_incident

router = APIRouter(prefix="/api", tags=["telemetry"])


@router.post("/telemetry")
async def ingest_telemetry(packet: TelemetryPacket, bg: BackgroundTasks):
    """Receive telemetry from edge client and route to prevention or incident path."""
    if packet.trigger_kind == TriggerKind.PREVENTION_CHECK:
        result = await handle_prevention(packet)
        return {"status": "prevention_processed", **result}

    elif packet.trigger_kind == TriggerKind.FALL_TRIGGER:
        result = await handle_incident(packet)
        return {"status": "incident_created", **result}

    else:
        result = await handle_prevention(packet)
        return {"status": "default_prevention", **result}
