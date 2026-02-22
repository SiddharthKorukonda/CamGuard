from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger("camguard.ws")

router = APIRouter()

_clients: set[WebSocket] = set()


async def broadcast(event: dict[str, Any]):
    """Broadcast an event to all connected WebSocket clients."""
    if not _clients:
        return

    def _serialize(obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return str(obj)

    message = json.dumps(event, default=_serialize)
    disconnected = set()
    for ws in _clients:
        try:
            await ws.send_text(message)
        except Exception:
            disconnected.add(ws)

    _clients.difference_update(disconnected)


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    _clients.add(ws)
    logger.info("WebSocket client connected (%d total)", len(_clients))
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        _clients.discard(ws)
        logger.info("WebSocket client disconnected (%d remaining)", len(_clients))
