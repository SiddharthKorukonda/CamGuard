from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ── Enums ──

class BedState(str, Enum):
    IN_BED = "IN_BED"
    NEAR_EDGE = "NEAR_EDGE"
    SITTING_EDGE = "SITTING_EDGE"
    LEGS_OVER = "LEGS_OVER"
    STANDING_NEAR_BED = "STANDING_NEAR_BED"
    OUT_OF_BED = "OUT_OF_BED"
    UNKNOWN = "UNKNOWN"


class Stability(str, Enum):
    STABLE = "STABLE"
    UNSTABLE = "UNSTABLE"
    UNKNOWN = "UNKNOWN"


class Verdict(str, Enum):
    NO_INCIDENT = "NO_INCIDENT"
    POSSIBLE_FALL = "POSSIBLE_FALL"
    CONFIRMED_FALL = "CONFIRMED_FALL"
    FALSE_ALARM = "FALSE_ALARM"


class ActionType(str, Enum):
    INCREASE_CHECK_RATE = "INCREASE_CHECK_RATE"
    SEND_LOW_PRIORITY_HEADSUP = "SEND_LOW_PRIORITY_HEADSUP"
    SEND_SMS_PRIMARY = "SEND_SMS_PRIMARY"
    START_VOICE_CALL_PRIMARY = "START_VOICE_CALL_PRIMARY"
    ESCALATE_TO_BACKUP = "ESCALATE_TO_BACKUP"
    CANCEL_ESCALATION = "CANCEL_ESCALATION"
    CLOSE_INCIDENT = "CLOSE_INCIDENT"
    REQUEST_STRONG_VERIFY = "REQUEST_STRONG_VERIFY"


class IncidentStatus(str, Enum):
    ACTIVE = "ACTIVE"
    ACKED = "ACKED"
    CLOSED = "CLOSED"


class TriggerKind(str, Enum):
    PREVENTION_CHECK = "PREVENTION_CHECK"
    FALL_TRIGGER = "FALL_TRIGGER"


class NotePriority(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


# ── Telemetry ──

class TelemetryPacket(BaseModel):
    camera_id: str
    ts: datetime
    room_type: str = "bedroom"
    bed_polygon: list[list[float]] = Field(default_factory=list)
    motion_energy: float = 0.0
    stillness_score: float = 0.0
    frames_jpeg_base64: list[str] = Field(default_factory=list)
    audio_pcm16_base64: Optional[str] = None
    language: Optional[str] = None
    person_present: Optional[bool] = None
    trigger_kind: Optional[TriggerKind] = None


# ── Bed Assessment ──

class BedAssessment(BaseModel):
    bed_state: BedState = BedState.UNKNOWN
    stability: Stability = Stability.UNKNOWN
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    notes: list[str] = Field(default_factory=list)


# ── Plan Action ──

class PlanAction(BaseModel):
    type: ActionType
    delay_s: float = 0.0
    params: dict = Field(default_factory=dict)


# ── Planner Plan ──

class PlannerPlan(BaseModel):
    verdict: Verdict = Verdict.POSSIBLE_FALL
    severity_seed: int = Field(default=3, ge=1, le=5)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    reasons: list[str] = Field(default_factory=list)
    actions: list[PlanAction] = Field(default_factory=list)
    replan_interval_s: float = Field(default=10.0, ge=1.0)


# ── Incident State (response model) ──

class IncidentStateResponse(BaseModel):
    incident_id: str = ""
    camera_id: str = ""
    created_at: Optional[datetime] = None
    status: IncidentStatus = IncidentStatus.ACTIVE
    verdict: str = ""
    severity_seed: int = 3
    severity_current: int = 3
    risk_score: float = 0.0
    confidence: float = 0.0
    time_down_s: float = 0.0
    acknowledged: bool = False
    ack_by: Optional[str] = None
    escalation_stage: int = 0
    plan_version: int = 0
    reasons_current: list[str] = Field(default_factory=list)
    language: str = "en"
    summary_text: Optional[str] = None

    class Config:
        from_attributes = True

    @classmethod
    def from_orm_incident(cls, inc) -> "IncidentStateResponse":
        return cls(
            incident_id=inc.id,
            camera_id=inc.camera_id,
            created_at=inc.created_at,
            status=inc.status,
            verdict=inc.verdict or "",
            severity_seed=inc.severity_seed,
            severity_current=inc.severity_current,
            risk_score=inc.risk_score,
            confidence=inc.confidence,
            time_down_s=inc.time_down_s,
            acknowledged=inc.acknowledged,
            ack_by=inc.ack_by,
            escalation_stage=inc.escalation_stage,
            plan_version=inc.plan_version,
            reasons_current=inc.reasons_current or [],
            language=inc.language,
            summary_text=inc.summary_text,
        )


# ── Camera registration ──

class CameraRegisterRequest(BaseModel):
    name: str = "Camera"
    room_type: str = "bedroom"
    bed_polygon: Optional[list[list[float]]] = None
    primary_contact: str = ""
    backup_contact: str = ""
    voice_enabled: bool = True
    sms_enabled: bool = True
    profile_id: Optional[str] = None


class CameraUpdateRequest(BaseModel):
    name: Optional[str] = None
    room_type: Optional[str] = None
    bed_polygon: Optional[list[list[float]]] = None
    primary_contact: Optional[str] = None
    backup_contact: Optional[str] = None
    voice_enabled: Optional[bool] = None
    sms_enabled: Optional[bool] = None
    config: Optional[dict] = None


class CameraResponse(BaseModel):
    id: str
    name: str
    room_type: str
    bed_polygon: Optional[list[list[float]]] = None
    primary_contact: str = ""
    backup_contact: str = ""
    voice_enabled: bool = True
    sms_enabled: bool = True
    status: str = "online"
    risk_score: float = 0.0
    last_seen: Optional[datetime] = None
    config: Optional[dict] = None

    class Config:
        from_attributes = True


# ── Agent monitoring instructions ──

class AgentInstructionRequest(BaseModel):
    camera_id: Optional[str] = None
    text: str
    priority: NotePriority = NotePriority.medium
    duration_minutes: int = 120


class AgentInstructionResponse(BaseModel):
    instruction_id: str
    summary: str
    parsed_watchlist: Optional[dict] = None


# ── Translate / TTS ──

class TranslateRequest(BaseModel):
    target_language: str = "es"
    text: Optional[str] = None


class TranslateResponse(BaseModel):
    translated_text: str
    language: str


class TTSRequest(BaseModel):
    text: Optional[str] = None
    language: Optional[str] = None


# ── Ack ──

class AckRequest(BaseModel):
    ack_by: str = "caregiver"


# ── Timeline event ──

class TimelineEvent(BaseModel):
    id: str
    incident_id: str
    camera_id: str
    kind: str
    ts: datetime
    payload: Optional[dict] = None

    class Config:
        from_attributes = True


# ── Summary ──

class IncidentSummaryResponse(BaseModel):
    summary_text: str
    reasons: list[str]
    plan_steps: list[dict]
    language: str
    verdict: str
    severity_current: int
    time_down_s: float
    escalation_stage: int
    acknowledged: bool
