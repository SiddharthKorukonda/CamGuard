"""Action executor: runs approved plan actions and logs results."""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone

from schemas import PlanAction, ActionType
from store.db import async_session
from store.models import ActionLog, Camera, Incident
from integrations import twilio_client, elevenlabs_client, snowflake_client
from core import logging as timeline_log

logger = logging.getLogger("camguard.executor")


async def execute_actions(
    actions: list[PlanAction],
    incident_id: str,
    camera_id: str,
    primary_contact: str,
    backup_contact: str,
    summary_text: str = "",
):
    """Execute a list of approved plan actions sequentially."""
    for action in actions:
        if action.delay_s > 0:
            await asyncio.sleep(action.delay_s)

        result = await _run_action(
            action, incident_id, camera_id,
            primary_contact, backup_contact, summary_text,
        )

        now = datetime.now(timezone.utc)
        action_id = str(uuid.uuid4())

        async with async_session() as db:
            log_entry = ActionLog(
                id=action_id,
                incident_id=incident_id,
                camera_id=camera_id,
                action_type=action.type.value,
                params=action.params,
                result=result,
                ts=now,
            )
            db.add(log_entry)
            await db.commit()

        snowflake_client.write_action_log(
            action_id=action_id,
            incident_id=incident_id,
            camera_id=camera_id,
            action_type=action.type.value,
            params=action.params,
            result=result,
            ts=now,
        )

        await timeline_log.log_event(
            incident_id=incident_id,
            camera_id=camera_id,
            kind="ACTION_EXECUTED",
            payload={"action_type": action.type.value, "result": result, "params": action.params},
        )


async def _run_action(
    action: PlanAction,
    incident_id: str,
    camera_id: str,
    primary_contact: str,
    backup_contact: str,
    summary_text: str,
) -> str:
    try:
        if action.type == ActionType.SEND_SMS_PRIMARY:
            body = f"🚨 CamGuard Alert: {summary_text or 'Possible fall detected.'} Incident: {incident_id[:8]}"
            sid = await twilio_client.send_sms(primary_contact, body)
            return f"SMS sent: {sid}"

        elif action.type == ActionType.SEND_LOW_PRIORITY_HEADSUP:
            body = f"ℹ️ CamGuard Heads-up: Risk score rising for camera {camera_id[:8]}. {summary_text}"
            sid = await twilio_client.send_sms(primary_contact, body)
            return f"Heads-up SMS sent: {sid}"

        elif action.type == ActionType.START_VOICE_CALL_PRIMARY:
            sid = await twilio_client.start_voice_call(primary_contact, incident_id)
            return f"Voice call started: {sid}"

        elif action.type == ActionType.ESCALATE_TO_BACKUP:
            body = f"🚨 CamGuard ESCALATION: {summary_text or 'Fall not acknowledged.'} Incident: {incident_id[:8]}"
            sid = await twilio_client.send_sms(backup_contact, body)
            call_sid = await twilio_client.start_voice_call(backup_contact, incident_id)
            return f"Escalated to backup: SMS={sid}, Call={call_sid}"

        elif action.type == ActionType.CANCEL_ESCALATION:
            return "Escalation cancelled"

        elif action.type == ActionType.CLOSE_INCIDENT:
            async with async_session() as db:
                from sqlalchemy import select
                result = await db.execute(select(Incident).where(Incident.id == incident_id))
                incident = result.scalar_one_or_none()
                if incident:
                    incident.status = "CLOSED"
                    await db.commit()
            return "Incident closed"

        elif action.type == ActionType.INCREASE_CHECK_RATE:
            new_interval = action.params.get("interval_s", 10)
            logger.info("Check rate increased to %ss for camera %s", new_interval, camera_id)
            return f"Check rate increased to {new_interval}s"

        elif action.type == ActionType.REQUEST_STRONG_VERIFY:
            return "Strong verification requested"

        else:
            return f"Unknown action type: {action.type}"

    except Exception as e:
        logger.error("Action execution error (%s): %s", action.type, e)
        return f"Error: {str(e)}"
