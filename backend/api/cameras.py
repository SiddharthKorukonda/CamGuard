from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from schemas import CameraRegisterRequest, CameraUpdateRequest, CameraResponse
from store.db import get_db
from store.models import Camera, NotificationPolicy, OnboardingConfig

logger = logging.getLogger("camguard.cameras")

router = APIRouter(prefix="/api/cameras", tags=["cameras"])


@router.get("", response_model=list[CameraResponse])
async def list_cameras(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Camera).order_by(Camera.created_at.desc()))
    cameras = result.scalars().all()
    return [CameraResponse.model_validate(c) for c in cameras]


@router.get("/{camera_id}", response_model=CameraResponse)
async def get_camera(camera_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Camera).where(Camera.id == camera_id))
    camera = result.scalar_one_or_none()
    if not camera:
        raise HTTPException(404, "Camera not found")
    return CameraResponse.model_validate(camera)


@router.post("/register", response_model=CameraResponse)
async def register_camera(req: CameraRegisterRequest, db: AsyncSession = Depends(get_db)):
    import uuid

    primary = req.primary_contact
    backup = req.backup_contact

    if not primary:
        onb_result = await db.execute(
            select(OnboardingConfig)
            .order_by(OnboardingConfig.created_at.desc())
            .limit(1)
        )
        onb = onb_result.scalar_one_or_none()
        if onb:
            primary = onb.primary_contact or ""
            backup = backup or onb.backup_contact or ""
            logger.info("Auto-populated camera contacts from onboarding config")

    cam_id = str(uuid.uuid4())
    camera = Camera(
        id=cam_id,
        name=req.name,
        room_type=req.room_type,
        bed_polygon=req.bed_polygon,
        primary_contact=primary,
        backup_contact=backup,
        voice_enabled=req.voice_enabled,
        sms_enabled=req.sms_enabled,
        profile_id=req.profile_id,
    )
    db.add(camera)

    policy = NotificationPolicy(
        camera_id=cam_id,
        sms_enabled=req.sms_enabled,
        voice_enabled=req.voice_enabled,
    )
    db.add(policy)
    await db.commit()
    await db.refresh(camera)
    return CameraResponse.model_validate(camera)


@router.patch("/{camera_id}", response_model=CameraResponse)
async def update_camera(camera_id: str, req: CameraUpdateRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Camera).where(Camera.id == camera_id))
    camera = result.scalar_one_or_none()
    if not camera:
        raise HTTPException(404, "Camera not found")

    for field, value in req.model_dump(exclude_unset=True).items():
        if field == "config" and value is not None:
            existing = dict(camera.config or {})
            existing.update(value)
            camera.config = existing
        else:
            setattr(camera, field, value)

    await db.commit()
    await db.refresh(camera)
    return CameraResponse.model_validate(camera)


@router.get("/{camera_id}/config")
async def get_camera_config(camera_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Camera).where(Camera.id == camera_id))
    camera = result.scalar_one_or_none()
    if not camera:
        raise HTTPException(404, "Camera not found")

    default_config = {
        "motion_spike_threshold": 0.7,
        "stillness_threshold": 0.8,
        "risk_threshold_low": 0.3,
        "risk_threshold_high": 0.7,
        "escalation_delay_s": 60,
        "check_interval_s": 30,
    }
    merged = {**default_config, **(camera.config or {})}
    return {"camera_id": camera_id, "config": merged}
