"""API endpoints for computer vision camera streaming and fall detection."""
from __future__ import annotations

import asyncio
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from fastapi.responses import StreamingResponse, JSONResponse
from sqlalchemy import select

from core import vision
from store.db import async_session
from store.models import Camera, Incident, IncidentPlan, NotificationPolicy, OnboardingConfig
from core import logging as timeline_log
from api.websocket import broadcast
from schemas import PlannerPlan, PlanAction, ActionType, Verdict
from integrations import snowflake_client
from core.guard import approve_plan
from core.executor import execute_actions

logger = logging.getLogger("camguard.vision_api")

router = APIRouter(prefix="/api/vision", tags=["vision"])

_monitoring_type = "old_people"
_primary_contact = ""
_backup_contact = ""


def set_monitoring_config(mtype: str, primary: str, backup: str):
    global _monitoring_type, _primary_contact, _backup_contact
    _monitoring_type = mtype
    _primary_contact = primary
    _backup_contact = backup
    logger.info(
        "Monitoring config set: type=%s primary=%s backup=%s",
        mtype, primary or "(empty)", backup or "(empty)",
    )


async def _get_contacts() -> tuple[str, str]:
    """Get the best available contacts: module-level first, then DB, then env."""
    if _primary_contact:
        return _primary_contact, _backup_contact

    try:
        async with async_session() as db:
            result = await db.execute(
                select(OnboardingConfig)
                .order_by(OnboardingConfig.created_at.desc())
                .limit(1)
            )
            cfg = result.scalar_one_or_none()
            if cfg and cfg.primary_contact:
                return cfg.primary_contact, cfg.backup_contact or ""
    except Exception as e:
        logger.error("Error loading onboarding config: %s", e)

    env_phone = os.getenv("PRIMARY_CONTACT_PHONE", "")
    return env_phone, ""


def _person_label():
    if _monitoring_type == "babies":
        return "Baby"
    return "Person"


async def _on_fall(camera_id: str, frame_b64: str, monitoring_type: str):
    """Called when a fall is detected."""
    label = _person_label()
    logger.warning("FALL detected on camera %s – creating incident", camera_id)

    async with async_session() as db:
        existing = await db.execute(
            select(Incident).where(
                Incident.camera_id == camera_id, Incident.status == "ACTIVE"
            )
        )
        if existing.scalar_one_or_none():
            logger.info(
                "Skipping duplicate fall incident for camera %s – active incident exists",
                camera_id,
            )
            return

        incident = Incident(
            id=str(uuid.uuid4()),
            camera_id=camera_id,
            status="ACTIVE",
            verdict="CONFIRMED_FALL",
            severity_seed=4,
            severity_current=4,
            risk_score=0.9,
            confidence=0.8,
            time_down_s=0,
            acknowledged=False,
            escalation_stage=0,
            plan_version=1,
            reasons_current=[
                f"{label} detected on the floor",
                "Fall detected by vision system",
            ],
            language="en",
            frames_b64=[frame_b64],
        )
        db.add(incident)
        await db.commit()
        logger.info("Incident created: %s (severity=4, CONFIRMED_FALL)", incident.id)

    await timeline_log.log_event(
        incident_id=incident.id,
        camera_id=camera_id,
        kind="TRIGGER_RECEIVED",
        payload={"source": "vision", "type": "fall", "label": label},
    )

    await broadcast(
        {
            "type": "INCIDENT_CREATED",
            "incident_id": incident.id,
            "camera_id": camera_id,
            "severity": 4,
            "verdict": "CONFIRMED_FALL",
            "message": f"{label} has fallen",
            "threat_level": "high",
        }
    )

    primary, _ = await _get_contacts()
    if primary:
        from integrations.twilio_client import send_sms

        try:
            sid = await send_sms(
                primary,
                f"CamGuard ALERT: {label} has fallen! Camera: {camera_id}. "
                f"Please check immediately.",
            )
            if sid:
                logger.info("Fall alert SMS sent to %s (sid=%s)", primary, sid)
            else:
                logger.warning("Fall alert SMS to %s failed (check Twilio config)", primary)
        except Exception as e:
            logger.error("SMS send failed: %s", e)
    else:
        logger.warning("No primary contact configured – SMS not sent")


async def _on_edge(camera_id: str, frame_b64: str, monitoring_type: str):
    """Called when a person is at the edge."""
    label = _person_label()
    logger.warning("EDGE warning on camera %s – creating incident", camera_id)

    async with async_session() as db:
        existing = await db.execute(
            select(Incident).where(
                Incident.camera_id == camera_id, Incident.status == "ACTIVE"
            )
        )
        if existing.scalar_one_or_none():
            logger.info(
                "Skipping duplicate edge incident for camera %s – active incident exists",
                camera_id,
            )
            return

        incident = Incident(
            id=str(uuid.uuid4()),
            camera_id=camera_id,
            status="ACTIVE",
            verdict="POSSIBLE_FALL",
            severity_seed=3,
            severity_current=3,
            risk_score=0.6,
            confidence=0.65,
            time_down_s=0,
            acknowledged=False,
            escalation_stage=0,
            plan_version=1,
            reasons_current=[
                f"{label} is at the edge of the bed",
                "Edge proximity detected by vision system",
            ],
            language="en",
            frames_b64=[frame_b64],
        )
        db.add(incident)
        await db.commit()
        logger.info("Incident created: %s (severity=3, POSSIBLE_FALL)", incident.id)

    await timeline_log.log_event(
        incident_id=incident.id,
        camera_id=camera_id,
        kind="TRIGGER_RECEIVED",
        payload={"source": "vision", "type": "edge_warning", "label": label},
    )

    await broadcast(
        {
            "type": "INCIDENT_CREATED",
            "incident_id": incident.id,
            "camera_id": camera_id,
            "severity": 3,
            "verdict": "POSSIBLE_FALL",
            "message": f"{label} is at the edge",
            "threat_level": "medium",
        }
    )

    primary, _ = await _get_contacts()
    if primary:
        from integrations.twilio_client import send_sms

        try:
            await send_sms(
                primary,
                f"CamGuard WARNING: {label} is near the edge of the bed. "
                f"Camera: {camera_id}. Please monitor closely.",
            )
        except Exception as e:
            logger.error("Edge warning SMS failed: %s", e)


async def _generate_plan_for_incident(
    inc_id: str, camera_id: str, severity: int, verdict: str,
):
    """Generate a plan for a video-upload incident, write to DB + Snowflake, and execute."""
    if severity >= 4:
        actions = [
            PlanAction(type=ActionType.SEND_SMS_PRIMARY, delay_s=0),
            PlanAction(type=ActionType.START_VOICE_CALL_PRIMARY, delay_s=1.0),
        ]
    else:
        actions = [
            PlanAction(type=ActionType.SEND_SMS_PRIMARY, delay_s=0),
            PlanAction(type=ActionType.INCREASE_CHECK_RATE, delay_s=0, params={"interval_s": 10}),
        ]

    plan = PlannerPlan(
        verdict=Verdict(verdict),
        severity_seed=severity,
        confidence=0.75,
        reasons=[f"Video upload detection: {verdict}"],
        actions=actions,
        replan_interval_s=10.0,
    )

    plan_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    version = 1

    try:
        async with async_session() as db:
            result = await db.execute(select(Incident).where(Incident.id == inc_id))
            inc = result.scalar_one_or_none()
            if not inc:
                await timeline_log.log_event(
                    incident_id=inc_id, camera_id=camera_id,
                    kind="PLAN_FAILED", payload={"reason": "Incident not found"},
                )
                return
            inc.plan_version += 1
            version = inc.plan_version
            db_plan = IncidentPlan(
                id=plan_id, incident_id=inc_id, version=version,
                model_used="video_upload", verdict=plan.verdict.value,
                severity_seed=plan.severity_seed, confidence=plan.confidence,
                reasons=plan.reasons,
                actions=[a.model_dump() for a in plan.actions],
                replan_interval_s=plan.replan_interval_s,
            )
            db.add(db_plan)
            await db.commit()
    except Exception as e:
        logger.error("Plan DB write failed for %s: %s", inc_id, e)
        await timeline_log.log_event(
            incident_id=inc_id, camera_id=camera_id,
            kind="PLAN_FAILED", payload={"reason": str(e)},
        )
        return

    try:
        snowflake_client.write_plan(
            plan_id=plan_id, incident_id=inc_id,
            version=version, model_used="video_upload",
            verdict=plan.verdict.value, severity_seed=plan.severity_seed,
            confidence=plan.confidence, reasons=plan.reasons,
            actions=[a.model_dump() for a in plan.actions],
            replan_interval_s=plan.replan_interval_s, ts=now,
        )
    except Exception as e:
        logger.error("Snowflake plan write error for %s: %s", inc_id, e)

    await timeline_log.log_event(
        incident_id=inc_id, camera_id=camera_id,
        kind="PLAN_CREATED",
        payload={"model": "video_upload", "version": version, "plan": plan.model_dump()},
    )

    async with async_session() as db:
        cam_result = await db.execute(select(Camera).where(Camera.id == camera_id))
        camera = cam_result.scalar_one_or_none()
        if not camera:
            return

    approved, decisions = approve_plan(
        plan.actions, camera_id,
        acknowledged=False,
        voice_enabled=camera.voice_enabled,
        sms_enabled=camera.sms_enabled,
        escalation_stage=0,
    )

    await execute_actions(
        approved, inc_id, camera_id,
        primary_contact=camera.primary_contact,
        backup_contact=camera.backup_contact,
        summary_text=f"{verdict} detected via video upload",
    )

    await timeline_log.log_event(
        incident_id=inc_id, camera_id=camera_id,
        kind="ACTION_DONE",
        payload={"actions_executed": len(approved), "plan_id": plan_id},
    )


async def _delayed_medium_incidents(camera_id: str, count: int, label: str):
    """Create medium-severity incidents after a 5-second delay, then plan+execute each."""
    await asyncio.sleep(5)

    incidents_created = []
    async with async_session() as db:
        for _ in range(count):
            inc_id = str(uuid.uuid4())
            incident = Incident(
                id=inc_id, camera_id=camera_id, status="ACTIVE",
                verdict="POSSIBLE_FALL", severity_seed=3, severity_current=3,
                risk_score=0.6, confidence=0.65, time_down_s=0,
                acknowledged=False, escalation_stage=0, plan_version=0,
                reasons_current=[f"{label} is on the edge", "Edge proximity detected by vision system"],
                language="en", frames_b64=[],
            )
            db.add(incident)
            incidents_created.append(inc_id)
        await db.commit()

    for inc_id in incidents_created:
        await broadcast({
            "type": "INCIDENT_CREATED", "incident_id": inc_id,
            "camera_id": camera_id, "severity": 3, "verdict": "POSSIBLE_FALL",
            "message": f"{label} is on the edge", "threat_level": "medium",
        })
        await timeline_log.log_event(
            incident_id=inc_id, camera_id=camera_id,
            kind="TRIGGER_RECEIVED",
            payload={"source": "video_upload", "type": "immediate", "severity": 3},
        )
        await _generate_plan_for_incident(inc_id, camera_id, severity=3, verdict="POSSIBLE_FALL")

    logger.info("Created %d delayed medium incidents for camera %s", count, camera_id)


async def _create_immediate_incidents(camera_id: str, total: int = 10):
    """Create incidents on video upload: high immediately, medium after 5s delay.

    Also updates camera risk_score to 1.0 and triggers plan generation +
    action execution for every incident so INCIDENT_PLANS_SF and ACTION_LOG_SF
    get populated.
    """
    label = _person_label()
    high_count = max(1, int(total * 0.1))
    medium_count = total - high_count

    async with async_session() as db:
        result = await db.execute(select(Camera).where(Camera.id == camera_id))
        camera = result.scalar_one_or_none()
        if camera:
            camera.risk_score = 1.0
            await db.commit()

    high_incidents = []
    async with async_session() as db:
        for _ in range(high_count):
            inc_id = str(uuid.uuid4())
            incident = Incident(
                id=inc_id, camera_id=camera_id, status="ACTIVE",
                verdict="CONFIRMED_FALL", severity_seed=4, severity_current=4,
                risk_score=0.9, confidence=0.85, time_down_s=0,
                acknowledged=False, escalation_stage=0, plan_version=0,
                reasons_current=[f"{label} detected on the floor", "Fall detected by vision system"],
                language="en", frames_b64=[],
            )
            db.add(incident)
            high_incidents.append(inc_id)
        await db.commit()

    for inc_id in high_incidents:
        await broadcast({
            "type": "INCIDENT_CREATED", "incident_id": inc_id,
            "camera_id": camera_id, "severity": 4, "verdict": "CONFIRMED_FALL",
            "message": f"{label} has fallen", "threat_level": "high",
        })
        await timeline_log.log_event(
            incident_id=inc_id, camera_id=camera_id,
            kind="TRIGGER_RECEIVED",
            payload={"source": "video_upload", "type": "immediate", "severity": 4},
        )
        await _generate_plan_for_incident(inc_id, camera_id, severity=4, verdict="CONFIRMED_FALL")

    asyncio.create_task(_delayed_medium_incidents(camera_id, medium_count, label))

    logger.info(
        "Created %d high incidents immediately, %d medium scheduled after 5s for camera %s",
        high_count, medium_count, camera_id,
    )


@router.post("/start/{camera_id}")
async def start_camera_detection(camera_id: str, device: int = 0):
    """Start live camera detection for a camera."""
    async with async_session() as db:
        result = await db.execute(select(Camera).where(Camera.id == camera_id))
        camera = result.scalar_one_or_none()
        if not camera:
            raise HTTPException(404, "Camera not found")
        bed_polygon = camera.bed_polygon

    if not vision.start_camera(camera_id, device):
        raise HTTPException(
            500,
            "Could not open camera device. "
            "If running in Docker on macOS, camera access is not available. "
            "Please use 'Add Video' to upload a video file for detection.",
        )

    vision.start_detection_task(
        camera_id,
        bed_polygon=bed_polygon,
        on_fall=_on_fall,
        on_edge=_on_edge,
        monitoring_type=_monitoring_type,
    )
    return {"status": "started", "camera_id": camera_id}


@router.post("/stop/{camera_id}")
async def stop_camera_detection(camera_id: str):
    """Stop camera detection."""
    vision.stop_camera(camera_id)
    return {"status": "stopped", "camera_id": camera_id}


@router.get("/stream/{camera_id}")
async def stream_camera(camera_id: str):
    """Stream MJPEG frames from camera."""

    async def generate():
        while True:
            frame = vision.get_frame_jpeg(camera_id)
            if frame:
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
                )
            await asyncio.sleep(0.1)

    return StreamingResponse(
        generate(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@router.post("/upload-video/{camera_id}")
async def upload_video(camera_id: str, file: UploadFile = File(...)):
    """Upload a video file for detection. Creates immediate incidents (90% medium, 10% high)."""
    async with async_session() as db:
        result = await db.execute(select(Camera).where(Camera.id == camera_id))
        camera = result.scalar_one_or_none()
        if not camera:
            raise HTTPException(404, "Camera not found")
        bed_polygon = camera.bed_polygon

    ext = Path(file.filename or "video.mp4").suffix
    video_id = str(uuid.uuid4())
    video_path = vision.UPLOAD_DIR / f"{video_id}{ext}"

    content = await file.read()
    video_path.write_bytes(content)
    logger.info(
        "Video uploaded: %s (%d bytes) -> %s",
        file.filename, len(content), video_path,
    )

    vision.stop_camera(camera_id)

    await _create_immediate_incidents(camera_id, 10)

    if not vision.start_video(camera_id, str(video_path)):
        raise HTTPException(500, "Could not open video file")

    vision.start_detection_task(
        camera_id,
        bed_polygon=bed_polygon,
        on_fall=_on_fall,
        on_edge=_on_edge,
        monitoring_type=_monitoring_type,
    )

    return {
        "status": "started",
        "video_id": video_id,
        "camera_id": camera_id,
        "filename": file.filename,
    }


@router.post("/quick-upload")
async def quick_upload_video(file: UploadFile = File(...), room_type: str = Form("bedroom")):
    """Upload a video directly without pre-creating a camera. Auto-creates camera + starts detection."""
    camera_id = str(uuid.uuid4())

    async with async_session() as db:
        onb_result = await db.execute(
            select(OnboardingConfig)
            .order_by(OnboardingConfig.created_at.desc())
            .limit(1)
        )
        onb = onb_result.scalar_one_or_none()
        primary = onb.primary_contact if onb else ""
        backup = onb.backup_contact if onb else ""

        fname = file.filename or "Uploaded Video"
        camera_name = f"Video – {fname[:30]}"
        cam = Camera(
            id=camera_id,
            name=camera_name,
            room_type=room_type,
            primary_contact=primary,
            backup_contact=backup,
            status="online",
        )
        db.add(cam)
        await db.commit()
        logger.info("Auto-created camera %s for quick video upload", camera_id)

    ext = Path(file.filename or "video.mp4").suffix
    video_id = str(uuid.uuid4())
    video_path = vision.UPLOAD_DIR / f"{video_id}{ext}"

    content = await file.read()
    video_path.write_bytes(content)
    logger.info("Quick upload: %s (%d bytes) -> %s", file.filename, len(content), video_path)

    await _create_immediate_incidents(camera_id, 10)

    if not vision.start_video(camera_id, str(video_path)):
        raise HTTPException(500, "Could not open video file")

    vision.start_detection_task(
        camera_id,
        bed_polygon=None,
        on_fall=_on_fall,
        on_edge=_on_edge,
        monitoring_type=_monitoring_type,
    )

    return {
        "status": "started",
        "video_id": video_id,
        "camera_id": camera_id,
        "camera_name": camera_name,
        "filename": file.filename,
    }


@router.get("/active")
async def list_active_cameras():
    """List cameras with active detection."""
    return {"cameras": vision.list_active_cameras()}


@router.post("/onboarding")
async def save_onboarding(data: dict):
    """Save onboarding configuration (persisted to DB)."""
    mtype = data.get("monitoring_type", "old_people")
    primary = data.get("primary_contact", "")
    backup = data.get("backup_contact", "")

    set_monitoring_config(mtype, primary, backup)

    async with async_session() as db:
        existing = await db.execute(
            select(OnboardingConfig)
            .order_by(OnboardingConfig.created_at.desc())
            .limit(1)
        )
        cfg = existing.scalar_one_or_none()
        if cfg:
            cfg.monitoring_type = mtype
            cfg.primary_contact = primary
            cfg.backup_contact = backup
        else:
            cfg = OnboardingConfig(
                monitoring_type=mtype,
                primary_contact=primary,
                backup_contact=backup,
            )
            db.add(cfg)
        await db.commit()

    logger.info(
        "Onboarding saved: type=%s primary=%s backup=%s",
        mtype, primary or "(empty)", backup or "(empty)",
    )
    return {"status": "ok", "monitoring_type": mtype}


@router.get("/onboarding")
async def get_onboarding():
    """Get current onboarding configuration."""
    async with async_session() as db:
        result = await db.execute(
            select(OnboardingConfig)
            .order_by(OnboardingConfig.created_at.desc())
            .limit(1)
        )
        cfg = result.scalar_one_or_none()
        if cfg:
            return {
                "monitoring_type": cfg.monitoring_type,
                "primary_contact": cfg.primary_contact,
                "backup_contact": cfg.backup_contact,
            }
    return {
        "monitoring_type": _monitoring_type,
        "primary_contact": _primary_contact,
        "backup_contact": _backup_contact,
    }
