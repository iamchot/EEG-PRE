"""
WebSocket connection manager for real-time EEG status broadcasting.
Manages multiple client connections per session.
"""

from __future__ import annotations

import asyncio
import json
from typing import Optional

from fastapi import WebSocket

# Active sessions: session_id → list of connected WebSocket clients
_sessions: dict[str, list[WebSocket]] = {}


async def connect(session_id: str, websocket: WebSocket) -> None:
    await websocket.accept()
    if session_id not in _sessions:
        _sessions[session_id] = []
    _sessions[session_id].append(websocket)


def disconnect(session_id: str, websocket: WebSocket) -> None:
    if session_id in _sessions:
        _sessions[session_id] = [
            ws for ws in _sessions[session_id] if ws is not websocket
        ]
        if not _sessions[session_id]:
            del _sessions[session_id]


async def broadcast(session_id: str, message: dict) -> None:
    """Send message to all clients subscribed to this session."""
    if session_id not in _sessions:
        return
    data = json.dumps(message)
    dead: list[WebSocket] = []
    for ws in _sessions[session_id]:
        try:
            await ws.send_text(data)
        except Exception:
            dead.append(ws)
    for ws in dead:
        disconnect(session_id, ws)


async def send_to(websocket: WebSocket, message: dict) -> None:
    """Send message to a single WebSocket client."""
    try:
        await websocket.send_text(json.dumps(message))
    except Exception:
        pass
