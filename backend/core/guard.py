"""SafetyGuard: hard rules that gate every plan before execution."""

from __future__ import annotations

import logging
import time
from typing import Optional

from schemas import PlanAction, ActionType

logger = logging.getLogger("camguard.guard")

_last_contact_time: dict[str, float] = {}
_primary_call_counts: dict[str, int] = {}


def reset_camera_state(camera_id: str):
    _last_contact_time.pop(camera_id, None)
    _primary_call_counts.pop(camera_id, None)


def approve_plan(
    actions: list[PlanAction],
    camera_id: str,
    acknowledged: bool,
    voice_enabled: bool,
    sms_enabled: bool,
    escalation_stage: int,
    cooldown_contact_s: int = 5,
    max_primary_call_attempts: int = 2,
    max_escalation_stage: int = 2,
) -> tuple[list[PlanAction], list[dict]]:
    """Filter actions through safety rules.
    Returns (approved_actions, guard_decisions)."""

    approved: list[PlanAction] = []
    decisions: list[dict] = []
    now = time.time()

    for action in actions:
        decision = {"action": action.type.value, "approved": True, "reason": ""}

        if action.type == ActionType.CLOSE_INCIDENT:
            approved.append(action)
            decisions.append(decision)
            continue

        if action.type == ActionType.CANCEL_ESCALATION:
            approved.append(action)
            decisions.append(decision)
            continue

        if action.type in (ActionType.SEND_SMS_PRIMARY, ActionType.START_VOICE_CALL_PRIMARY,
                           ActionType.SEND_LOW_PRIORITY_HEADSUP):
            last_contact = _last_contact_time.get(camera_id, 0)
            if now - last_contact < cooldown_contact_s:
                decision["approved"] = False
                decision["reason"] = f"Contact cooldown: {cooldown_contact_s}s not elapsed"
                decisions.append(decision)
                continue

        if action.type == ActionType.START_VOICE_CALL_PRIMARY:
            if not voice_enabled:
                decision["approved"] = False
                decision["reason"] = "Voice disabled for this camera"
                decisions.append(decision)
                continue
            call_count = _primary_call_counts.get(camera_id, 0)
            if call_count >= max_primary_call_attempts:
                decision["approved"] = False
                decision["reason"] = f"Max primary call attempts ({max_primary_call_attempts}) reached"
                decisions.append(decision)
                continue

        if action.type == ActionType.SEND_SMS_PRIMARY:
            if not sms_enabled:
                decision["approved"] = False
                decision["reason"] = "SMS disabled for this camera"
                decisions.append(decision)
                continue

        if action.type == ActionType.ESCALATE_TO_BACKUP:
            if acknowledged:
                decision["approved"] = False
                decision["reason"] = "Already acknowledged – no backup escalation"
                decisions.append(decision)
                continue
            if escalation_stage >= max_escalation_stage:
                decision["approved"] = False
                decision["reason"] = f"Max escalation stage ({max_escalation_stage}) reached"
                decisions.append(decision)
                continue

        approved.append(action)
        decisions.append(decision)

        if action.type in (ActionType.SEND_SMS_PRIMARY, ActionType.START_VOICE_CALL_PRIMARY,
                           ActionType.SEND_LOW_PRIORITY_HEADSUP, ActionType.ESCALATE_TO_BACKUP):
            _last_contact_time[camera_id] = now

        if action.type == ActionType.START_VOICE_CALL_PRIMARY:
            _primary_call_counts[camera_id] = _primary_call_counts.get(camera_id, 0) + 1

    dropped = [d for d in decisions if not d["approved"]]
    if dropped:
        logger.info("Guard dropped %d actions for camera %s: %s", len(dropped), camera_id, dropped)

    return approved, decisions
