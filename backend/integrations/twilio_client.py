from __future__ import annotations

import logging
import os
from typing import Optional

from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse, Gather

logger = logging.getLogger("camguard.twilio")

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER", "")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000")


def _get_client() -> Client:
    return Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)


async def send_sms(to_number: str, body: str) -> Optional[str]:
    """Send an SMS via Twilio. Returns message SID or None on failure."""
    if not TWILIO_ACCOUNT_SID or TWILIO_ACCOUNT_SID.startswith("your-"):
        logger.warning("Twilio not configured – SMS would be sent to %s: %s", to_number, body)
        return "MOCK_SMS_SID"

    try:
        client = _get_client()
        message = client.messages.create(
            body=body,
            from_=TWILIO_FROM_NUMBER,
            to=to_number,
        )
        logger.info("SMS sent: %s -> %s", message.sid, to_number)
        return message.sid
    except Exception as e:
        logger.error("SMS send failed: %s", e)
        return None


async def start_voice_call(to_number: str, incident_id: str) -> Optional[str]:
    """Initiate a voice call with DTMF menu. Returns call SID or None."""
    if not TWILIO_ACCOUNT_SID or TWILIO_ACCOUNT_SID.startswith("your-"):
        logger.warning("Twilio not configured – call would go to %s for incident %s", to_number, incident_id)
        return "MOCK_CALL_SID"

    try:
        client = _get_client()
        call = client.calls.create(
            url=f"{PUBLIC_BASE_URL}/twilio/voice/{incident_id}",
            to=to_number,
            from_=TWILIO_FROM_NUMBER,
            method="POST",
        )
        logger.info("Voice call started: %s -> %s", call.sid, to_number)
        return call.sid
    except Exception as e:
        logger.error("Voice call failed: %s", e)
        return None


def build_voice_twiml(incident_id: str, audio_url: Optional[str] = None) -> str:
    """Build TwiML for the voice call with DTMF gather."""
    response = VoiceResponse()
    gather = Gather(
        num_digits=1,
        action=f"{PUBLIC_BASE_URL}/twilio/dtmf/{incident_id}",
        method="POST",
        timeout=10,
    )

    if audio_url:
        gather.play(audio_url)
    else:
        gather.say(
            "CamGuard alert. A fall has been detected. "
            "Press 1 to acknowledge. "
            "Press 2 to call the person. "
            "Press 3 to escalate to backup. "
            "Press 4 to mark false alarm.",
            voice="Polly.Joanna",
        )

    response.append(gather)
    response.say("We didn't receive any input. Goodbye.", voice="Polly.Joanna")
    return str(response)
