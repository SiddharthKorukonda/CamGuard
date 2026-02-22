from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from schemas import (
    IncidentStateResponse, AckRequest, IncidentSummaryResponse,
)
from store.db import get_db
from store.models import Incident, IncidentPlan, IncidentTimeline
from core.planner import cancel_replan, _generate_summary
from core import logging as timeline_log
from core.guard import reset_camera_state

router = APIRouter(prefix="/api/incidents", tags=["incidents"])


@router.get("", response_model=list[IncidentStateResponse])
async def list_incidents(
    status: Optional[str] = None,
    severity_min: Optional[int] = None,
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
):
    query = select(Incident).order_by(desc(Incident.created_at)).limit(limit)
    if status:
        query = query.where(Incident.status == status.upper())
    if severity_min:
        query = query.where(Incident.severity_current >= severity_min)

    result = await db.execute(query)
    incidents = result.scalars().all()
    return [IncidentStateResponse.from_orm_incident(i) for i in incidents]


@router.get("/{incident_id}", response_model=IncidentStateResponse)
async def get_incident(incident_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Incident).where(Incident.id == incident_id))
    incident = result.scalar_one_or_none()
    if not incident:
        raise HTTPException(404, "Incident not found")
    return IncidentStateResponse.from_orm_incident(incident)


@router.post("/{incident_id}/ack")
async def acknowledge_incident(incident_id: str, req: AckRequest = AckRequest(), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Incident).where(Incident.id == incident_id))
    incident = result.scalar_one_or_none()
    if not incident:
        raise HTTPException(404, "Incident not found")

    incident.acknowledged = True
    incident.ack_by = req.ack_by
    incident.status = "ACKED"
    await db.commit()

    cancel_replan(incident_id)
    reset_camera_state(incident.camera_id)

    await timeline_log.log_event(
        incident_id=incident_id,
        camera_id=incident.camera_id,
        kind="ACK_RECEIVED",
        payload={"ack_by": req.ack_by},
    )

    return {"status": "acknowledged", "incident_id": incident_id}


@router.post("/{incident_id}/false_alarm")
async def false_alarm(incident_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Incident).where(Incident.id == incident_id))
    incident = result.scalar_one_or_none()
    if not incident:
        raise HTTPException(404, "Incident not found")

    incident.status = "CLOSED"
    incident.verdict = "FALSE_ALARM"
    incident.acknowledged = True
    await db.commit()

    cancel_replan(incident_id)
    reset_camera_state(incident.camera_id)

    await timeline_log.log_event(
        incident_id=incident_id,
        camera_id=incident.camera_id,
        kind="CLOSED",
        payload={"reason": "false_alarm"},
    )

    return {"status": "closed", "reason": "false_alarm"}


@router.get("/{incident_id}/timeline")
async def get_incident_timeline(incident_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(IncidentTimeline)
        .where(IncidentTimeline.incident_id == incident_id)
        .order_by(IncidentTimeline.ts)
    )
    events = result.scalars().all()
    return [
        {
            "id": e.id, "incident_id": e.incident_id, "camera_id": e.camera_id,
            "kind": e.kind, "ts": e.ts.isoformat() if e.ts else "",
            "payload": e.payload,
        }
        for e in events
    ]


@router.get("/{incident_id}/plan")
async def get_incident_plans(incident_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(IncidentPlan)
        .where(IncidentPlan.incident_id == incident_id)
        .order_by(desc(IncidentPlan.version))
    )
    plans = result.scalars().all()
    return [
        {
            "id": p.id, "incident_id": p.incident_id, "version": p.version,
            "model_used": p.model_used, "verdict": p.verdict,
            "severity_seed": p.severity_seed, "confidence": p.confidence,
            "reasons": p.reasons, "actions": p.actions,
            "replan_interval_s": p.replan_interval_s,
            "created_at": p.created_at.isoformat() if p.created_at else "",
        }
        for p in plans
    ]


@router.get("/{incident_id}/frames")
async def get_incident_frames(incident_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Incident).where(Incident.id == incident_id))
    incident = result.scalar_one_or_none()
    if not incident:
        raise HTTPException(404, "Incident not found")
    return {"incident_id": incident_id, "frames_b64": incident.frames_b64 or []}


@router.get("/{incident_id}/summary", response_model=IncidentSummaryResponse)
async def get_incident_summary(incident_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Incident).where(Incident.id == incident_id))
    incident = result.scalar_one_or_none()
    if not incident:
        raise HTTPException(404, "Incident not found")

    plans_result = await db.execute(
        select(IncidentPlan)
        .where(IncidentPlan.incident_id == incident_id)
        .order_by(desc(IncidentPlan.version))
        .limit(1)
    )
    latest_plan = plans_result.scalar_one_or_none()
    plan_steps = latest_plan.actions if latest_plan and latest_plan.actions else []

    summary = incident.summary_text or _generate_summary(incident)

    return IncidentSummaryResponse(
        summary_text=summary,
        reasons=incident.reasons_current or [],
        plan_steps=plan_steps,
        language=incident.language,
        verdict=incident.verdict,
        severity_current=incident.severity_current,
        time_down_s=incident.time_down_s,
        escalation_stage=incident.escalation_stage,
        acknowledged=incident.acknowledged,
    )
