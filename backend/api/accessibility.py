from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from schemas import TranslateRequest, TranslateResponse, TTSRequest
from store.db import get_db
from store.models import Incident
from integrations import gemini_client, elevenlabs_client
from core import logging as timeline_log
from core.planner import _generate_summary

router = APIRouter(prefix="/api/incidents", tags=["accessibility"])


@router.post("/{incident_id}/translate", response_model=TranslateResponse)
async def translate_incident(
    incident_id: str,
    req: TranslateRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Incident).where(Incident.id == incident_id))
    incident = result.scalar_one_or_none()
    if not incident:
        raise HTTPException(404, "Incident not found")

    source_text = req.text or incident.summary_text or _generate_summary(incident)

    translated = await gemini_client.translate_text(source_text, req.target_language)

    await timeline_log.log_event(
        incident_id=incident_id,
        camera_id=incident.camera_id,
        kind="TRANSLATED",
        payload={
            "target_language": req.target_language,
            "original_length": len(source_text),
            "translated_length": len(translated),
        },
    )

    return TranslateResponse(translated_text=translated, language=req.target_language)


@router.post("/{incident_id}/tts")
async def text_to_speech(
    incident_id: str,
    req: TTSRequest = TTSRequest(),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Incident).where(Incident.id == incident_id))
    incident = result.scalar_one_or_none()
    if not incident:
        raise HTTPException(404, "Incident not found")

    text = req.text or incident.summary_text or _generate_summary(incident)

    audio_bytes = await elevenlabs_client.text_to_speech(text)

    await timeline_log.log_event(
        incident_id=incident_id,
        camera_id=incident.camera_id,
        kind="TTS_GENERATED",
        payload={"text_length": len(text), "audio_bytes": len(audio_bytes)},
    )

    return Response(
        content=audio_bytes,
        media_type="audio/mpeg",
        headers={"Content-Disposition": f"inline; filename=incident_{incident_id[:8]}.mp3"},
    )


@router.post("/translate-text", response_model=TranslateResponse)
async def translate_text_endpoint(req: TranslateRequest):
    """Translate arbitrary text (for page translation)."""
    if not req.text:
        return TranslateResponse(translated_text="", language=req.target_language)
    translated = await gemini_client.translate_text(req.text, req.target_language)
    return TranslateResponse(translated_text=translated, language=req.target_language)


@router.post("/translate-batch")
async def translate_batch_endpoint(data: dict):
    """Batch translate multiple texts for page-wide translation."""
    texts = data.get("texts", [])
    target_language = data.get("target_language", "en")
    if not texts or target_language == "en":
        return {"translations": texts, "language": target_language}
    translations = await gemini_client.batch_translate(texts, target_language)
    return {"translations": translations, "language": target_language}
