from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    JSON,
    Enum as SAEnum,
)
from sqlalchemy.orm import Mapped, mapped_column

from store.db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


# ── Profiles ──

class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), default="")
    language: Mapped[str] = mapped_column(String(10), default="en")
    sensitivity: Mapped[str] = mapped_column(String(20), default="medium")
    privacy_retention_days: Mapped[int] = mapped_column(Integer, default=30)
    escalation_timing_s: Mapped[int] = mapped_column(Integer, default=60)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


# ── Cameras ──

class Camera(Base):
    __tablename__ = "cameras"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255), default="Camera")
    room_type: Mapped[str] = mapped_column(String(50), default="bedroom")
    bed_polygon: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    primary_contact: Mapped[str] = mapped_column(String(50), default="")
    backup_contact: Mapped[str] = mapped_column(String(50), default="")
    voice_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    sms_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    profile_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    last_seen: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="online")
    risk_score: Mapped[float] = mapped_column(Float, default=0.0)
    config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, default=lambda: {
        "motion_spike_threshold": 0.7,
        "stillness_threshold": 0.8,
        "risk_threshold_low": 0.3,
        "risk_threshold_high": 0.7,
        "escalation_delay_s": 60,
        "check_interval_s": 30,
    })
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


# ── Notification Policies ──

class NotificationPolicy(Base):
    __tablename__ = "notification_policies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    camera_id: Mapped[str] = mapped_column(String(36), index=True)
    sms_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    voice_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    escalation_delay_s: Mapped[int] = mapped_column(Integer, default=60)
    cooldown_contact_s: Mapped[int] = mapped_column(Integer, default=5)
    max_primary_call_attempts: Mapped[int] = mapped_column(Integer, default=2)
    language: Mapped[str] = mapped_column(String(10), default="en")


# ── Incidents ──

class Incident(Base):
    __tablename__ = "incidents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    camera_id: Mapped[str] = mapped_column(String(36), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE")
    verdict: Mapped[str] = mapped_column(String(30), default="POSSIBLE_FALL")
    severity_seed: Mapped[int] = mapped_column(Integer, default=3)
    severity_current: Mapped[int] = mapped_column(Integer, default=3)
    risk_score: Mapped[float] = mapped_column(Float, default=0.5)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    time_down_s: Mapped[float] = mapped_column(Float, default=0.0)
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)
    ack_by: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    escalation_stage: Mapped[int] = mapped_column(Integer, default=0)
    plan_version: Mapped[int] = mapped_column(Integer, default=0)
    reasons_current: Mapped[Optional[list]] = mapped_column(JSON, nullable=True, default=list)
    language: Mapped[str] = mapped_column(String(10), default="en")
    summary_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    frames_b64: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)


# ── Incident Plans ──

class IncidentPlan(Base):
    __tablename__ = "incident_plans"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    incident_id: Mapped[str] = mapped_column(String(36), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    model_used: Mapped[str] = mapped_column(String(50), default="fast")
    verdict: Mapped[str] = mapped_column(String(30), default="")
    severity_seed: Mapped[int] = mapped_column(Integer, default=3)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    reasons: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    actions: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    replan_interval_s: Mapped[float] = mapped_column(Float, default=10.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


# ── Incident Timeline ──

class IncidentTimeline(Base):
    __tablename__ = "incident_timeline"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    incident_id: Mapped[str] = mapped_column(String(36), index=True)
    camera_id: Mapped[str] = mapped_column(String(36), default="")
    kind: Mapped[str] = mapped_column(String(50))
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)


# ── Action Log ──

class ActionLog(Base):
    __tablename__ = "action_log"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    incident_id: Mapped[str] = mapped_column(String(36), index=True)
    camera_id: Mapped[str] = mapped_column(String(36), default="")
    action_type: Mapped[str] = mapped_column(String(50))
    params: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    result: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


# ── Config Updates ──

class ConfigUpdate(Base):
    __tablename__ = "config_updates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    camera_id: Mapped[str] = mapped_column(String(36), index=True)
    reason: Mapped[str] = mapped_column(Text, default="")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    config_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    applied: Mapped[bool] = mapped_column(Boolean, default=False)
    rolled_back: Mapped[bool] = mapped_column(Boolean, default=False)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


# ── Onboarding Config ──

class OnboardingConfig(Base):
    __tablename__ = "onboarding_config"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    monitoring_type: Mapped[str] = mapped_column(String(50), default="old_people")
    primary_contact: Mapped[str] = mapped_column(String(50), default="")
    backup_contact: Mapped[str] = mapped_column(String(50), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


# ── Agent Notes (AI Chat monitoring instructions) ──

class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(String(36), index=True, default="")
    role: Mapped[str] = mapped_column(String(20), default="user")
    text: Mapped[str] = mapped_column(Text, default="")
    camera_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class PerformanceMetric(Base):
    __tablename__ = "performance_metrics"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    metric_type: Mapped[str] = mapped_column(String(50), default="")
    metric_name: Mapped[str] = mapped_column(String(100), default="")
    value: Mapped[float] = mapped_column(Float, default=0.0)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class AgentNote(Base):
    __tablename__ = "agent_notes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    camera_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    text: Mapped[str] = mapped_column(Text, default="")
    priority: Mapped[str] = mapped_column(String(10), default="medium")
    parsed_watchlist: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    summary: Mapped[str] = mapped_column(Text, default="")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
