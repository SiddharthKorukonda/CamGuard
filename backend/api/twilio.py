from __future__ import annotations

from fastapi import APIRouter, Form, Depends
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from store.db import get_db
from store.models import Incident
from integrations.twilio_client import build_voice_twiml
from core.planner import cancel_replan, _generate_summary
from core.guard import reset_camera_state
from core import logging as timeline_log

router = APIRouter(prefix="/twilio", tags=["twilio"])


@router.post("/voice/{incident_id}")
async def voice_webhook(incident_id: str, db: AsyncSession = Depends(get_db)):
    """Return TwiML for Twilio voice call with DTMF gathering."""
    result = await db.execute(select(Incident).where(Incident.id == incident_id))
    incident = result.scalar_one_or_none()

    summary = ""
    if incident:
        summary = incident.summary_text or _generate_summary(incident)

    twiml = build_voice_twiml(incident_id)
    return Response(content=twiml, media_type="application/xml")


@router.post("/dtmf/{incident_id}")
async def dtmf_webhook(
    incident_id: str,
    Digits: str = Form(""),
    db: AsyncSession = Depends(get_db),
):
    """Handle DTMF digit presses from Twilio voice call.
    1 = acknowledge, 2 = will call person, 3 = escalate to backup, 4 = false alarm."""
    result = await db.execute(select(Incident).where(Incident.id == incident_id))
    incident = result.scalar_one_or_none()
    if not incident:
        return Response(content="<Response><Say>Incident not found.</Say></Response>", media_type="application/xml")

    digit = Digits.strip()

    if digit == "1":
        incident.acknowledged = True
        incident.ack_by = "voice_dtmf"
        incident.status = "ACKED"
        await db.commit()
        cancel_replan(incident_id)
        reset_camera_state(incident.camera_id)
        await timeline_log.log_event(
            incident_id=incident_id, camera_id=incident.camera_id,
            kind="ACK_RECEIVED", payload={"ack_by": "voice_dtmf", "digit": "1"},
        )
        msg = "Acknowledged. Escalation cancelled. Thank you."

    elif digit == "2":
        incident.acknowledged = True
        incident.ack_by = "voice_dtmf_will_call"
        incident.status = "ACKED"
        await db.commit()
        cancel_replan(incident_id)
        await timeline_log.log_event(
            incident_id=incident_id, camera_id=incident.camera_id,
            kind="ACK_RECEIVED", payload={"ack_by": "voice_dtmf_will_call", "digit": "2"},
        )
        msg = "Noted. You will call the monitored person. Escalation paused."

    elif digit == "3":
        incident.escalation_stage = min(incident.escalation_stage + 1, 2)
        await db.commit()
        await timeline_log.log_event(
            incident_id=incident_id, camera_id=incident.camera_id,
            kind="ESCALATION", payload={"stage": incident.escalation_stage, "digit": "3"},
        )
        msg = "Escalating to backup contact now."

    elif digit == "4":
        incident.status = "CLOSED"
        incident.verdict = "FALSE_ALARM"
        incident.acknowledged = True
        await db.commit()
        cancel_replan(incident_id)
        reset_camera_state(incident.camera_id)
        await timeline_log.log_event(
            incident_id=incident_id, camera_id=incident.camera_id,
            kind="CLOSED", payload={"reason": "false_alarm_dtmf", "digit": "4"},
        )
        msg = "Marked as false alarm. Incident closed."

    else:
        msg = "Invalid option. Goodbye."

    twiml = f"<Response><Say voice='Polly.Joanna'>{msg}</Say></Response>"
    return Response(content=twiml, media_type="application/xml")
