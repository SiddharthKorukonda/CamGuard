"""Agentic planner: orchestrates the observe-plan-guard-execute loop."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select

from schemas import (
    TelemetryPacket, BedAssessment, PlannerPlan, PlanAction,
    ActionType, Verdict, BedState, Stability,
)
from store.db import async_session
from store.models import Incident, IncidentPlan, Camera, NotificationPolicy, AgentNote
from integrations import gemini_client, snowflake_client
from core import logging as timeline_log
from core.severity import compute_severity, compute_risk_score
from core.guard import approve_plan
from core.executor import execute_actions

logger = logging.getLogger("camguard.planner")

_active_replan_tasks: dict[str, asyncio.Task] = {}


def _build_policy_text(policy: NotificationPolicy | None, camera: Camera) -> str:
    if policy:
        return (
            f"sms_enabled={policy.sms_enabled}, voice_enabled={policy.voice_enabled}, "
            f"escalation_delay_s={policy.escalation_delay_s}, cooldown_contact_s={policy.cooldown_contact_s}, "
            f"max_primary_call_attempts={policy.max_primary_call_attempts}"
        )
    return (
        f"sms_enabled={camera.sms_enabled}, voice_enabled={camera.voice_enabled}, "
        f"escalation_delay_s={camera.config.get('escalation_delay_s', 60) if camera.config else 60}, "
        f"cooldown_contact_s=5, max_primary_call_attempts=2"
    )


async def _get_active_notes(camera_id: str) -> list[str]:
    now = datetime.now(timezone.utc)
    async with async_session() as db:
        result = await db.execute(
            select(AgentNote).where(
                AgentNote.expires_at > now,
                (AgentNote.camera_id == camera_id) | (AgentNote.camera_id.is_(None)),
            )
        )
        notes = result.scalars().all()
        return [n.text for n in notes]


def _build_incident_state(incident: Incident) -> dict:
    return {
        "incident_id": incident.id,
        "status": incident.status,
        "severity_seed": incident.severity_seed,
        "severity_current": incident.severity_current,
        "time_down_s": incident.time_down_s,
        "acknowledged": incident.acknowledged,
        "escalation_stage": incident.escalation_stage,
        "plan_version": incident.plan_version,
        "reasons_current": incident.reasons_current or [],
    }


def _parse_plan(raw: str) -> PlannerPlan | None:
    try:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
        data = json.loads(cleaned)
        return PlannerPlan(**data)
    except Exception as e:
        logger.error("Plan parse error: %s from raw: %s", e, raw[:200])
        return None


def _fallback_plan(motion_energy: float, voice_enabled: bool) -> PlannerPlan:
    sev = 4 if motion_energy > 0.8 else 3
    actions = [PlanAction(type=ActionType.SEND_SMS_PRIMARY, delay_s=0)]
    if voice_enabled and sev >= 4:
        actions.append(PlanAction(type=ActionType.START_VOICE_CALL_PRIMARY, delay_s=1.0))
    return PlannerPlan(
        verdict=Verdict.POSSIBLE_FALL,
        severity_seed=sev,
        confidence=0.3,
        reasons=["Fallback plan: Gemini unavailable or returned invalid response"],
        actions=actions,
        replan_interval_s=5.0,
    )


def needs_strong_verify(plan: PlannerPlan) -> bool:
    if plan.verdict == Verdict.POSSIBLE_FALL and plan.confidence < 0.6:
        return True
    if plan.severity_seed >= 4 and plan.confidence < 0.7:
        return True
    return False


def _generate_summary(incident: Incident) -> str:
    reasons_text = "; ".join((incident.reasons_current or [])[:3]) or "Monitoring in progress"
    ack_status = "acknowledged" if incident.acknowledged else "not yet acknowledged"
    return (
        f"{incident.verdict} detected (severity {incident.severity_current}/5). "
        f"Time since event: {incident.time_down_s:.0f}s. {reasons_text}. "
        f"Escalation stage {incident.escalation_stage}. Status: {ack_status}."
    )


async def handle_prevention(packet: TelemetryPacket):
    """Prevention path: bed assessment → risk score → optional low-risk plan."""
    logger.info("Prevention check for camera %s", packet.camera_id)

    raw_assessment = await gemini_client.bed_assessment(
        frames_b64=packet.frames_jpeg_base64[:4],
        bed_polygon=packet.bed_polygon,
        room_type=packet.room_type,
    )

    assessment = None
    try:
        data = json.loads(raw_assessment.strip().lstrip("```json").rstrip("```"))
        assessment = BedAssessment(**data)
    except Exception:
        assessment = BedAssessment()

    hour = datetime.now().hour
    risk_score = compute_risk_score(
        bed_state=assessment.bed_state.value,
        stability=assessment.stability.value,
        hour_of_day=hour,
    )

    async with async_session() as db:
        result = await db.execute(select(Camera).where(Camera.id == packet.camera_id))
        camera = result.scalar_one_or_none()
        if camera:
            camera.risk_score = risk_score
            camera.last_seen = datetime.now(timezone.utc)
            await db.commit()

    dummy_incident_id = f"prev-{packet.camera_id[:8]}-{uuid.uuid4().hex[:8]}"

    await timeline_log.log_event(
        incident_id=dummy_incident_id, camera_id=packet.camera_id,
        kind="BED_ASSESSMENT",
        payload={"bed_state": assessment.bed_state.value, "stability": assessment.stability.value,
                 "confidence": assessment.confidence, "notes": assessment.notes},
    )
    await timeline_log.log_event(
        incident_id=dummy_incident_id, camera_id=packet.camera_id,
        kind="RISK_UPDATED", payload={"risk_score": risk_score},
    )

    config = {}
    async with async_session() as db:
        result = await db.execute(select(Camera).where(Camera.id == packet.camera_id))
        camera = result.scalar_one_or_none()
        if camera and camera.config:
            config = camera.config

    threshold_high = config.get("risk_threshold_high", 0.7)
    if risk_score >= threshold_high:
        agent_notes = await _get_active_notes(packet.camera_id)

        async with async_session() as db:
            result = await db.execute(select(Camera).where(Camera.id == packet.camera_id))
            camera = result.scalar_one_or_none()
            pol_result = await db.execute(
                select(NotificationPolicy).where(NotificationPolicy.camera_id == packet.camera_id)
            )
            policy = pol_result.scalar_one_or_none()
            policy_text = _build_policy_text(policy, camera) if camera else ""

        raw_plan = await gemini_client.incident_plan(
            frames_b64=packet.frames_jpeg_base64[:4],
            motion_energy=packet.motion_energy,
            stillness_score=packet.stillness_score,
            room_type=packet.room_type,
            policy_text=policy_text,
            incident_state={"mode": "prevention", "risk_score": risk_score},
            agent_notes=agent_notes,
            mode="prevention",
        )

        plan = _parse_plan(raw_plan)
        if not plan:
            plan = PlannerPlan(
                verdict=Verdict.NO_INCIDENT,
                severity_seed=1,
                confidence=0.5,
                reasons=["Risk score elevated – increasing monitoring"],
                actions=[PlanAction(type=ActionType.INCREASE_CHECK_RATE, params={"interval_s": 10})],
                replan_interval_s=30.0,
            )

        await timeline_log.log_event(
            incident_id=dummy_incident_id, camera_id=packet.camera_id,
            kind="PLAN_CREATED", payload={"model": "fast", "plan": plan.model_dump()},
        )

        voice_en = camera.voice_enabled if camera else True
        sms_en = camera.sms_enabled if camera else True
        approved, decisions = approve_plan(
            plan.actions, packet.camera_id,
            acknowledged=False, voice_enabled=voice_en, sms_enabled=sms_en,
            escalation_stage=0,
        )

        await timeline_log.log_event(
            incident_id=dummy_incident_id, camera_id=packet.camera_id,
            kind="PLAN_APPROVED", payload={"decisions": decisions},
        )

        await execute_actions(
            approved, dummy_incident_id, packet.camera_id,
            primary_contact=camera.primary_contact if camera else "",
            backup_contact=camera.backup_contact if camera else "",
            summary_text=f"Risk score elevated to {risk_score:.2f}",
        )

    return {
        "risk_score": risk_score,
        "bed_state": assessment.bed_state.value,
        "stability": assessment.stability.value,
        "confidence": assessment.confidence,
    }


async def handle_incident(packet: TelemetryPacket) -> dict:
    """Incident path: create incident → plan → guard → execute → replan loop."""
    logger.info("Fall trigger for camera %s", packet.camera_id)

    async with async_session() as db:
        result = await db.execute(select(Camera).where(Camera.id == packet.camera_id))
        camera = result.scalar_one_or_none()
        if not camera:
            return {"error": "Camera not found"}

        existing = await db.execute(
            select(Incident).where(
                Incident.camera_id == packet.camera_id,
                Incident.status == "ACTIVE",
            )
        )
        active_incident = existing.scalar_one_or_none()

        if active_incident:
            incident = active_incident
        else:
            incident = Incident(
                camera_id=packet.camera_id,
                severity_seed=3,
                severity_current=3,
                risk_score=0.8,
                frames_b64=packet.frames_jpeg_base64[:4],
                language=packet.language or camera.config.get("language", "en") if camera.config else "en",
            )
            db.add(incident)
            await db.commit()
            await db.refresh(incident)

        pol_result = await db.execute(
            select(NotificationPolicy).where(NotificationPolicy.camera_id == packet.camera_id)
        )
        policy = pol_result.scalar_one_or_none()

    await timeline_log.log_event(
        incident_id=incident.id, camera_id=packet.camera_id,
        kind="TRIGGER_RECEIVED",
        payload={"trigger_kind": "FALL_TRIGGER", "motion_energy": packet.motion_energy,
                 "stillness_score": packet.stillness_score},
    )

    policy_text = _build_policy_text(policy, camera)
    agent_notes = await _get_active_notes(packet.camera_id)
    incident_state = _build_incident_state(incident)

    raw_plan = await gemini_client.incident_plan(
        frames_b64=packet.frames_jpeg_base64[:4],
        motion_energy=packet.motion_energy,
        stillness_score=packet.stillness_score,
        room_type=packet.room_type,
        policy_text=policy_text,
        incident_state=incident_state,
        agent_notes=agent_notes,
        mode="incident",
    )

    plan = _parse_plan(raw_plan)
    retry_count = 0
    if not plan and retry_count == 0:
        retry_count += 1
        try:
            raw_plan = await gemini_client.incident_plan(
                frames_b64=packet.frames_jpeg_base64[:2],
                motion_energy=packet.motion_energy,
                stillness_score=packet.stillness_score,
                room_type=packet.room_type,
                policy_text=policy_text,
                incident_state=incident_state,
                agent_notes=agent_notes,
                mode="incident",
            )
            plan = _parse_plan(raw_plan)
        except Exception:
            pass

    if not plan:
        plan = _fallback_plan(packet.motion_energy, camera.voice_enabled)

    plan_id = str(uuid.uuid4())
    async with async_session() as db:
        result = await db.execute(select(Incident).where(Incident.id == incident.id))
        inc = result.scalar_one()
        inc.plan_version += 1
        inc.severity_seed = plan.severity_seed
        inc.severity_current = plan.severity_seed
        inc.verdict = plan.verdict.value
        inc.confidence = plan.confidence
        inc.reasons_current = plan.reasons
        inc.summary_text = _generate_summary(inc)
        await db.commit()

        db_plan = IncidentPlan(
            id=plan_id,
            incident_id=incident.id,
            version=inc.plan_version,
            model_used="fast",
            verdict=plan.verdict.value,
            severity_seed=plan.severity_seed,
            confidence=plan.confidence,
            reasons=plan.reasons,
            actions=[a.model_dump() for a in plan.actions],
            replan_interval_s=plan.replan_interval_s,
        )
        db.add(db_plan)
        await db.commit()

    snowflake_client.write_plan(
        plan_id=plan_id, incident_id=incident.id,
        version=inc.plan_version, model_used="fast",
        verdict=plan.verdict.value, severity_seed=plan.severity_seed,
        confidence=plan.confidence, reasons=plan.reasons,
        actions=[a.model_dump() for a in plan.actions],
        replan_interval_s=plan.replan_interval_s,
        ts=datetime.now(timezone.utc),
    )

    await timeline_log.log_event(
        incident_id=incident.id, camera_id=packet.camera_id,
        kind="PLAN_CREATED",
        payload={"model": "fast", "version": inc.plan_version, "plan": plan.model_dump()},
    )

    approved, decisions = approve_plan(
        plan.actions, packet.camera_id,
        acknowledged=incident.acknowledged,
        voice_enabled=camera.voice_enabled,
        sms_enabled=camera.sms_enabled,
        escalation_stage=incident.escalation_stage,
    )

    await timeline_log.log_event(
        incident_id=incident.id, camera_id=packet.camera_id,
        kind="PLAN_APPROVED", payload={"decisions": decisions},
    )

    await execute_actions(
        approved, incident.id, packet.camera_id,
        primary_contact=camera.primary_contact,
        backup_contact=camera.backup_contact,
        summary_text=incident.summary_text or _generate_summary(incident),
    )

    if needs_strong_verify(plan):
        asyncio.create_task(_strong_verify_task(incident.id, packet, plan))

    _start_replan_loop(incident.id, packet.camera_id, plan.replan_interval_s)
    _start_severity_ticker(incident.id, packet.camera_id)

    return {
        "incident_id": incident.id,
        "plan_version": inc.plan_version,
        "verdict": plan.verdict.value,
        "severity": plan.severity_seed,
        "actions_executed": len(approved),
    }


async def _strong_verify_task(incident_id: str, packet: TelemetryPacket, current_plan: PlannerPlan):
    try:
        async with async_session() as db:
            result = await db.execute(select(Incident).where(Incident.id == incident_id))
            incident = result.scalar_one_or_none()
            if not incident:
                return

        raw = await gemini_client.strong_verify(
            frames_b64=packet.frames_jpeg_base64[:4],
            motion_energy=packet.motion_energy,
            stillness_score=packet.stillness_score,
            current_plan=current_plan.model_dump(),
            incident_state=_build_incident_state(incident),
        )

        strong_plan = _parse_plan(raw)
        if not strong_plan:
            return

        plan_id = str(uuid.uuid4())
        async with async_session() as db:
            result = await db.execute(select(Incident).where(Incident.id == incident_id))
            inc = result.scalar_one()
            inc.plan_version += 1
            inc.verdict = strong_plan.verdict.value
            inc.confidence = strong_plan.confidence
            inc.reasons_current = strong_plan.reasons
            inc.summary_text = _generate_summary(inc)
            await db.commit()

            db_plan = IncidentPlan(
                id=plan_id, incident_id=incident_id,
                version=inc.plan_version, model_used="strong",
                verdict=strong_plan.verdict.value,
                severity_seed=strong_plan.severity_seed,
                confidence=strong_plan.confidence,
                reasons=strong_plan.reasons,
                actions=[a.model_dump() for a in strong_plan.actions],
                replan_interval_s=strong_plan.replan_interval_s,
            )
            db.add(db_plan)
            await db.commit()

        snowflake_client.write_plan(
            plan_id=plan_id, incident_id=incident_id,
            version=inc.plan_version, model_used="strong",
            verdict=strong_plan.verdict.value, severity_seed=strong_plan.severity_seed,
            confidence=strong_plan.confidence, reasons=strong_plan.reasons,
            actions=[a.model_dump() for a in strong_plan.actions],
            replan_interval_s=strong_plan.replan_interval_s,
            ts=datetime.now(timezone.utc),
        )

        await timeline_log.log_event(
            incident_id=incident_id, camera_id=packet.camera_id,
            kind="PLAN_CREATED",
            payload={"model": "strong", "version": inc.plan_version, "plan": strong_plan.model_dump()},
        )

    except Exception as e:
        logger.error("Strong verify failed: %s", e)


def _start_replan_loop(incident_id: str, camera_id: str, interval_s: float):
    if incident_id in _active_replan_tasks:
        _active_replan_tasks[incident_id].cancel()

    async def _replan():
        while True:
            await asyncio.sleep(interval_s)
            try:
                async with async_session() as db:
                    result = await db.execute(select(Incident).where(Incident.id == incident_id))
                    incident = result.scalar_one_or_none()
                    if not incident or incident.status != "ACTIVE":
                        break

                    cam_result = await db.execute(select(Camera).where(Camera.id == camera_id))
                    camera = cam_result.scalar_one_or_none()
                    if not camera:
                        break

                    pol_result = await db.execute(
                        select(NotificationPolicy).where(NotificationPolicy.camera_id == camera_id)
                    )
                    policy = pol_result.scalar_one_or_none()

                policy_text = _build_policy_text(policy, camera)
                agent_notes = await _get_active_notes(camera_id)

                raw = await gemini_client.incident_plan(
                    frames_b64=incident.frames_b64 or [],
                    motion_energy=0.3,
                    stillness_score=0.7,
                    room_type=camera.room_type,
                    policy_text=policy_text,
                    incident_state=_build_incident_state(incident),
                    agent_notes=agent_notes,
                    mode="incident",
                )

                plan = _parse_plan(raw)
                if not plan:
                    plan = _fallback_plan(0.3, camera.voice_enabled)

                plan_id = str(uuid.uuid4())
                async with async_session() as db:
                    result = await db.execute(select(Incident).where(Incident.id == incident_id))
                    inc = result.scalar_one()
                    inc.plan_version += 1
                    inc.reasons_current = plan.reasons
                    inc.summary_text = _generate_summary(inc)
                    await db.commit()

                    db_plan = IncidentPlan(
                        id=plan_id, incident_id=incident_id,
                        version=inc.plan_version, model_used="fast",
                        verdict=plan.verdict.value,
                        severity_seed=plan.severity_seed,
                        confidence=plan.confidence,
                        reasons=plan.reasons,
                        actions=[a.model_dump() for a in plan.actions],
                        replan_interval_s=plan.replan_interval_s,
                    )
                    db.add(db_plan)
                    await db.commit()

                await timeline_log.log_event(
                    incident_id=incident_id, camera_id=camera_id,
                    kind="REPLAN",
                    payload={"version": inc.plan_version, "plan": plan.model_dump()},
                )

                approved, decisions = approve_plan(
                    plan.actions, camera_id,
                    acknowledged=incident.acknowledged,
                    voice_enabled=camera.voice_enabled,
                    sms_enabled=camera.sms_enabled,
                    escalation_stage=incident.escalation_stage,
                )

                config = camera.config or {}
                esc_delay = config.get("escalation_delay_s", 60)
                if (not incident.acknowledged and incident.time_down_s > esc_delay
                        and incident.escalation_stage < 2):
                    esc_action = PlanAction(type=ActionType.ESCALATE_TO_BACKUP, delay_s=0)
                    esc_approved, esc_decisions = approve_plan(
                        [esc_action], camera_id,
                        acknowledged=incident.acknowledged,
                        voice_enabled=camera.voice_enabled,
                        sms_enabled=camera.sms_enabled,
                        escalation_stage=incident.escalation_stage,
                    )
                    if esc_approved:
                        approved.extend(esc_approved)
                        async with async_session() as db:
                            result = await db.execute(select(Incident).where(Incident.id == incident_id))
                            inc2 = result.scalar_one()
                            inc2.escalation_stage += 1
                            await db.commit()
                        await timeline_log.log_event(
                            incident_id=incident_id, camera_id=camera_id,
                            kind="ESCALATION",
                            payload={"stage": incident.escalation_stage + 1},
                        )

                await execute_actions(
                    approved, incident_id, camera_id,
                    primary_contact=camera.primary_contact,
                    backup_contact=camera.backup_contact,
                    summary_text=incident.summary_text or "",
                )

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Replan loop error: %s", e)
                await asyncio.sleep(5)

    task = asyncio.create_task(_replan())
    _active_replan_tasks[incident_id] = task


def _start_severity_ticker(incident_id: str, camera_id: str):
    async def _tick():
        while True:
            await asyncio.sleep(1.0)
            try:
                async with async_session() as db:
                    result = await db.execute(select(Incident).where(Incident.id == incident_id))
                    incident = result.scalar_one_or_none()
                    if not incident or incident.status != "ACTIVE":
                        break

                    incident.time_down_s += 1.0
                    new_sev = compute_severity(
                        severity_seed=incident.severity_seed,
                        time_down_s=incident.time_down_s,
                        stillness_score=0.7,
                        motion_energy=0.1,
                        acknowledged=incident.acknowledged,
                    )
                    old_sev = incident.severity_current
                    incident.severity_current = new_sev
                    incident.summary_text = _generate_summary(incident)
                    await db.commit()

                if new_sev != old_sev or int(incident.time_down_s) % 5 == 0:
                    await timeline_log.log_event(
                        incident_id=incident_id, camera_id=camera_id,
                        kind="SEVERITY_TICK",
                        payload={"severity_current": new_sev, "time_down_s": incident.time_down_s},
                    )
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Severity tick error: %s", e)

    asyncio.create_task(_tick())


def cancel_replan(incident_id: str):
    task = _active_replan_tasks.pop(incident_id, None)
    if task:
        task.cancel()
