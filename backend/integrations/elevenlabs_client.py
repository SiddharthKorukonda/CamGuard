from __future__ import annotations

import logging
import os

import httpx

logger = logging.getLogger("camguard.elevenlabs")

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")

TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech"


async def text_to_speech(text: str, voice_id: str | None = None) -> bytes:
    """Generate speech audio from text using ElevenLabs TTS API.
    Returns MP3 bytes."""
    vid = voice_id or ELEVENLABS_VOICE_ID
    url = f"{TTS_URL}/{vid}"

    headers = {
        "xi-api-key": ELEVENLABS_API_KEY,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }

    payload = {
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75,
            "style": 0.0,
            "use_speaker_boost": True,
        },
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        return resp.content


async def generate_call_audio(incident_summary: str) -> bytes:
    """Generate the spoken message for a Twilio voice call."""
    call_text = (
        f"CamGuard alert. {incident_summary} "
        "Press 1 to acknowledge and stop escalation. "
        "Press 2 if you will call the monitored person. "
        "Press 3 to escalate to backup contact now. "
        "Press 4 to mark this as a false alarm."
    )
    return await text_to_speech(call_text)
