from __future__ import annotations

import json
import logging
import os
from typing import Optional

import httpx

logger = logging.getLogger("camguard.gemini")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL_FAST = os.getenv("GEMINI_MODEL_FAST", "gemini-2.5-flash-lite")
GEMINI_MODEL_STRONG = os.getenv("GEMINI_MODEL_STRONG", "gemini-2.5-pro")

BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"


def _api_url(model: str) -> str:
    return f"{BASE_URL}/{model}:generateContent?key={GEMINI_API_KEY}"


def _build_image_part(frame_b64: str) -> dict:
    return {
        "inline_data": {
            "mime_type": "image/jpeg",
            "data": frame_b64,
        }
    }


async def _call_gemini(model: str, prompt: str, frames_b64: list[str] | None = None) -> str:
    parts: list[dict] = []
    if frames_b64:
        for f in frames_b64[:4]:
            parts.append(_build_image_part(f))
    parts.append({"text": prompt})

    payload = {
        "contents": [{"parts": parts}],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 2048,
            "responseMimeType": "application/json" if "json" in prompt.lower()[:200] else "text/plain",
        },
    }

    if "respond with valid json" in prompt.lower() or "strict json" in prompt.lower():
        payload["generationConfig"]["responseMimeType"] = "application/json"

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(_api_url(model), json=payload)
        resp.raise_for_status()
        data = resp.json()

    candidates = data.get("candidates", [])
    if not candidates:
        raise ValueError("No candidates returned from Gemini")
    content = candidates[0].get("content", {})
    text_parts = [p.get("text", "") for p in content.get("parts", [])]
    return "".join(text_parts)


async def bed_assessment(frames_b64: list[str], bed_polygon: list[list[float]], room_type: str = "bedroom") -> str:
    prompt = f"""You are a bed-state assessment agent for a caregiver camera in a {room_type}.
Analyze the provided camera frames and the bed polygon coordinates: {json.dumps(bed_polygon)}.

Determine the person's position relative to the bed.

Respond with valid JSON matching this exact schema:
{{
  "bed_state": one of ["IN_BED", "NEAR_EDGE", "SITTING_EDGE", "LEGS_OVER", "STANDING_NEAR_BED", "OUT_OF_BED", "UNKNOWN"],
  "stability": one of ["STABLE", "UNSTABLE", "UNKNOWN"],
  "confidence": float 0.0 to 1.0,
  "notes": [list of brief observation strings]
}}

Only output the JSON object, nothing else."""
    return await _call_gemini(GEMINI_MODEL_FAST, prompt, frames_b64)


async def incident_plan(
    frames_b64: list[str],
    motion_energy: float,
    stillness_score: float,
    room_type: str,
    policy_text: str,
    incident_state: dict,
    agent_notes: list[str] | None = None,
    mode: str = "incident",
) -> str:
    notes_section = ""
    if agent_notes:
        notes_section = f"\n\nActive caregiver monitoring instructions:\n" + "\n".join(f"- {n}" for n in agent_notes)

    prompt = f"""You are an agentic fall triage planner for a caregiver camera system.
Mode: {mode}
Room type: {room_type}
Motion energy: {motion_energy}
Stillness score: {stillness_score}

Current incident state:
{json.dumps(incident_state, indent=2)}

Notification policy:
{policy_text}
{notes_section}

Analyze the camera frames and sensor data. Create an action plan.

Respond with valid JSON matching this strict schema:
{{
  "verdict": one of ["NO_INCIDENT", "POSSIBLE_FALL", "CONFIRMED_FALL", "FALSE_ALARM"],
  "severity_seed": integer 1-5,
  "confidence": float 0.0 to 1.0,
  "reasons": [list of string reasons],
  "actions": [
    {{
      "type": one of ["INCREASE_CHECK_RATE", "SEND_LOW_PRIORITY_HEADSUP", "SEND_SMS_PRIMARY", "START_VOICE_CALL_PRIMARY", "ESCALATE_TO_BACKUP", "CANCEL_ESCALATION", "CLOSE_INCIDENT", "REQUEST_STRONG_VERIFY"],
      "delay_s": float,
      "params": {{}}
    }}
  ],
  "replan_interval_s": float (seconds until next replan)
}}

Rules:
- For {mode} mode with high severity (4-5), include SEND_SMS_PRIMARY with delay_s=0
- If voice is enabled and severity >= 4, include START_VOICE_CALL_PRIMARY after SMS
- For prevention mode, only use INCREASE_CHECK_RATE or SEND_LOW_PRIORITY_HEADSUP
- Set replan_interval_s between 5 and 30 based on urgency

Only output the JSON object, nothing else."""
    return await _call_gemini(GEMINI_MODEL_FAST, prompt, frames_b64)


async def strong_verify(
    frames_b64: list[str],
    motion_energy: float,
    stillness_score: float,
    current_plan: dict,
    incident_state: dict,
) -> str:
    prompt = f"""You are a senior fall verification agent doing a careful second opinion.

Current plan verdict: {current_plan.get('verdict', 'UNKNOWN')}
Current plan confidence: {current_plan.get('confidence', 0)}
Motion energy: {motion_energy}
Stillness score: {stillness_score}
Incident state: {json.dumps(incident_state, indent=2)}

Carefully analyze the camera frames. Provide your refined assessment.

Respond with valid JSON matching this strict schema:
{{
  "verdict": one of ["NO_INCIDENT", "POSSIBLE_FALL", "CONFIRMED_FALL", "FALSE_ALARM"],
  "severity_seed": integer 1-5,
  "confidence": float 0.0 to 1.0,
  "reasons": [list of detailed string reasons],
  "actions": [action objects if any additional actions needed],
  "replan_interval_s": float
}}

Only output the JSON object, nothing else."""
    return await _call_gemini(GEMINI_MODEL_STRONG, prompt, frames_b64)


async def translate_text(text: str, target_language: str) -> str:
    prompt = f"""Translate the following text into {target_language}. 
Return only the translated text, no explanations or extra formatting.

Text to translate:
{text}"""
    return await _call_gemini(GEMINI_MODEL_FAST, prompt)


async def parse_agent_instruction(text: str, camera_id: Optional[str] = None) -> str:
    context = f" for camera {camera_id}" if camera_id else " globally"
    prompt = f"""You are an AI caregiver assistant. A caregiver has given monitoring instructions{context}.

Instruction: "{text}"

Parse this into a structured watchlist. Respond with valid JSON:
{{
  "summary": "brief summary of what to watch for",
  "parsed_watchlist": {{
    "conditions": [list of conditions to monitor],
    "risk_factors": [list of risk factors mentioned],
    "special_instructions": [list of special care instructions],
    "urgency": "low" or "medium" or "high"
  }}
}}

Only output the JSON object, nothing else."""
    return await _call_gemini(GEMINI_MODEL_FAST, prompt)


async def generate_summary(
    verdict: str,
    severity_current: int,
    time_down_s: float,
    reasons: list[str],
    escalation_stage: int,
    acknowledged: bool,
) -> str:
    top_reasons = reasons[:3] if reasons else ["No specific reasons available"]
    prompt = f"""Generate a concise incident summary for a caregiver.

Verdict: {verdict}
Severity: {severity_current}/5
Time since event: {time_down_s:.0f} seconds
Top reasons: {json.dumps(top_reasons)}
Escalation stage: {escalation_stage}
Acknowledged: {acknowledged}

Write 2-3 clear sentences summarizing the situation for a worried caregiver.
Use simple, calm language. Be factual, not alarming.
Return only the summary text."""
    return await _call_gemini(GEMINI_MODEL_FAST, prompt)


async def polish_report(reasons: list[str], verdict: str, incident_summary: str) -> str:
    prompt = f"""You are writing a final incident report.
Verdict: {verdict}
Summary: {incident_summary}
Raw reasons: {json.dumps(reasons)}

Polish these reasons into clear, professional incident report language.
Return a JSON array of polished reason strings.
Respond with valid JSON array only."""
    return await _call_gemini(GEMINI_MODEL_STRONG, prompt)


async def batch_translate(texts: list[str], target_language: str) -> list[str]:
    joined = "\n---SEPARATOR---\n".join(texts)
    prompt = f"""Translate each of the following text segments into {target_language}.
The segments are separated by "---SEPARATOR---".
Return the translations in the same order, separated by "---SEPARATOR---".
Only output the translated segments separated by ---SEPARATOR---, nothing else.

{joined}"""
    result = await _call_gemini(GEMINI_MODEL_FAST, prompt)
    parts = result.split("---SEPARATOR---")
    parts = [p.strip() for p in parts]
    while len(parts) < len(texts):
        parts.append(texts[len(parts)])
    return parts[:len(texts)]


async def chat_response(
    message: str,
    history: list[dict] | None = None,
    context: str | None = None,
) -> str:
    history_text = ""
    if history:
        for msg in history[-10:]:
            role = msg.get("role", "user")
            text = msg.get("text", "")
            history_text += f"\n{role.upper()}: {text}"

    context_section = ""
    if context:
        context_section = f"\n\nAdditional context from the monitoring system:\n{context}"

    prompt = f"""You are CamGuard AI, an intelligent caregiver assistant integrated into a comprehensive fall detection and monitoring system. You help caregivers monitor elderly patients and infants.

Your capabilities include:
- Analyzing camera feeds for fall detection and edge-of-bed warnings
- Managing incident response workflows with escalation protocols
- Sending SMS/voice alerts to emergency contacts via Twilio
- Providing real-time risk assessments using computer vision (YOLOv8)
- Translating content into 20+ languages for multilingual caregivers
- Generating detailed incident reports with timeline analysis

System features you can discuss:
- Real-time person detection and fall analysis using YOLOv8 computer vision
- Multi-level severity system (1-5) with automatic escalation
- Agentic planning with observe-plan-guard-execute loop
- Snowflake data warehouse integration for analytics and audit trails
- WebSocket-based real-time notifications
- Video upload for batch analysis of recorded footage

Be thorough, detailed, and empathetic in your responses. Provide actionable advice and explain monitoring concepts clearly. Use paragraphs, bullet points, and structured formatting when appropriate to make responses comprehensive and easy to read. Aim for responses that are informative and helpful, like a knowledgeable healthcare technology assistant would provide.
{context_section}

Conversation so far:{history_text}

USER: {message}

Provide a detailed, helpful response. Be thorough and informative."""
    return await _call_gemini(GEMINI_MODEL_FAST, prompt)
