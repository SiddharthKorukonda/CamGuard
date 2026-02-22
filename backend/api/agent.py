from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from schemas import AgentInstructionRequest, AgentInstructionResponse
from store.db import get_db, async_session
from store.models import AgentNote, ChatMessage, Incident, PerformanceMetric
from integrations import gemini_client, snowflake_client
from core import logging as timeline_log

logger = logging.getLogger("camguard.agent")

router = APIRouter(prefix="/api/agent", tags=["agent"])


@router.post("/monitoring-instructions", response_model=AgentInstructionResponse)
async def create_monitoring_instruction(
    req: AgentInstructionRequest,
    db: AsyncSession = Depends(get_db),
):
    """AI chat endpoint: caregiver sends monitoring instructions, Gemini parses them."""
    raw = await gemini_client.parse_agent_instruction(req.text, req.camera_id)

    parsed = {}
    summary = req.text
    try:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
        data = json.loads(cleaned)
        summary = data.get("summary", req.text)
        parsed = data.get("parsed_watchlist", {})
    except Exception:
        parsed = {"conditions": [req.text], "risk_factors": [], "special_instructions": [], "urgency": req.priority.value}

    now = datetime.now(timezone.utc)
    note = AgentNote(
        camera_id=req.camera_id,
        text=req.text,
        priority=req.priority.value,
        parsed_watchlist=parsed,
        summary=summary,
        expires_at=now + timedelta(minutes=req.duration_minutes),
    )
    db.add(note)
    await db.commit()
    await db.refresh(note)

    incident_id = f"agent-note-{note.id[:8]}"
    await timeline_log.log_event(
        incident_id=incident_id,
        camera_id=req.camera_id or "global",
        kind="AGENT_NOTE_CREATED",
        payload={"note_id": note.id, "summary": summary, "priority": req.priority.value},
    )

    snowflake_client.write_agent_log(
        log_id=str(uuid.uuid4()),
        camera_id=req.camera_id or "global",
        incident_id=incident_id,
        event_kind="AGENT_NOTE_CREATED",
        payload={"note_id": note.id, "text": req.text, "parsed": parsed},
        ts=now,
    )

    return AgentInstructionResponse(
        instruction_id=note.id,
        summary=summary,
        parsed_watchlist=parsed,
    )


@router.post("/chat")
async def chat_endpoint(data: dict):
    """Conversational AI chat with detailed responses."""
    message = data.get("message", "")
    session_id = data.get("session_id", str(uuid.uuid4()))
    camera_id = data.get("camera_id")
    history = data.get("history", [])

    if not message.strip():
        return {"response": "Please send a message.", "session_id": session_id}

    now = datetime.now(timezone.utc)

    async with async_session() as db:
        db.add(ChatMessage(
            session_id=session_id, role="user",
            text=message, camera_id=camera_id,
        ))
        await db.commit()

    context_parts = []
    try:
        async with async_session() as db:
            inc_count = await db.execute(select(func.count(Incident.id)))
            total_incidents = inc_count.scalar() or 0
            active_count = await db.execute(
                select(func.count(Incident.id)).where(Incident.status == "ACTIVE")
            )
            active_incidents = active_count.scalar() or 0
            context_parts.append(
                f"System status: {total_incidents} total incidents, {active_incidents} currently active."
            )
    except Exception:
        pass

    context = " ".join(context_parts) if context_parts else None

    start_time = datetime.now(timezone.utc)
    try:
        response_text = await gemini_client.chat_response(
            message=message, history=history, context=context,
        )
    except Exception as e:
        logger.error("Chat response error: %s", e)
        response_text = (
            "I'm currently experiencing a connection issue with my AI backend, "
            "but I'm still here to help. The CamGuard system is monitoring all cameras "
            "and will alert you to any incidents. Please try again in a moment."
        )
    elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()

    async with async_session() as db:
        db.add(ChatMessage(
            session_id=session_id, role="assistant",
            text=response_text, camera_id=camera_id,
        ))
        db.add(PerformanceMetric(
            metric_type="chat", metric_name="response_time_s",
            value=elapsed,
            metadata_json={"session_id": session_id, "message_length": len(message)},
        ))
        await db.commit()

    snowflake_client.write_agent_log(
        log_id=str(uuid.uuid4()),
        camera_id=camera_id or "global",
        incident_id="",
        event_kind="CHAT_MESSAGE",
        payload={
            "session_id": session_id,
            "user_message": message[:500],
            "response_length": len(response_text),
            "response_time_s": elapsed,
        },
        ts=now,
    )

    return {
        "response": response_text,
        "session_id": session_id,
    }


@router.get("/performance")
async def get_performance_metrics():
    """Get average performance metrics for agents and app."""
    async with async_session() as db:
        chat_times = await db.execute(
            select(func.avg(PerformanceMetric.value), func.count(PerformanceMetric.id))
            .where(PerformanceMetric.metric_name == "response_time_s")
        )
        row = chat_times.first()
        avg_chat_time = round(row[0] or 0, 2)
        total_chats = row[1] or 0

        detection_times = await db.execute(
            select(func.avg(PerformanceMetric.value), func.count(PerformanceMetric.id))
            .where(PerformanceMetric.metric_name == "detection_time_s")
        )
        det_row = detection_times.first()
        avg_detection_time = round(det_row[0] or 0, 2)
        total_detections = det_row[1] or 0

        total_incidents = await db.execute(select(func.count(Incident.id)))
        incident_count = total_incidents.scalar() or 0

        active_incidents = await db.execute(
            select(func.count(Incident.id)).where(Incident.status == "ACTIVE")
        )
        active_count = active_incidents.scalar() or 0

    metrics = {
        "avg_chat_response_time_s": avg_chat_time,
        "total_chat_messages": total_chats,
        "avg_detection_time_s": avg_detection_time,
        "total_detections": total_detections,
        "total_incidents": incident_count,
        "active_incidents": active_count,
        "uptime_status": "healthy",
    }

    snowflake_client.write_agent_log(
        log_id=str(uuid.uuid4()),
        camera_id="global",
        incident_id="",
        event_kind="PERFORMANCE_QUERY",
        payload=metrics,
        ts=datetime.now(timezone.utc),
    )

    return metrics
