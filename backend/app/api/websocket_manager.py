"""
WebSocket connection manager with thread-safe progress bridging.

Maintains a mapping of attack_id → WebSocket so the attack worker
thread can push progress to the correct client without blocking
the async event loop.
"""

from __future__ import annotations

import logging
from typing import Dict

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages active WebSocket connections keyed by attack_id."""

    def __init__(self) -> None:
        self._connections: Dict[str, WebSocket] = {}

    async def connect(self, attack_id: str, websocket: WebSocket) -> None:
        """Accept and store a new WebSocket connection."""
        await websocket.accept()
        self._connections[attack_id] = websocket
        logger.info("WebSocket connected for attack_id=%s (total=%d)", attack_id, len(self._connections))

    async def disconnect(self, attack_id: str) -> None:
        """Remove and close the WebSocket for the given attack_id, if present."""
        websocket = self._connections.pop(attack_id, None)
        if websocket is not None:
            try:
                await websocket.close()
            except Exception:
                pass  # connection may already be closed
            logger.info("WebSocket disconnected for attack_id=%s (total=%d)", attack_id, len(self._connections))

    async def send_progress(self, attack_id: str, message: dict) -> None:
        """Send a JSON message to the WebSocket for a specific attack_id.

        Silently ignores WebSocketDisconnect (client left) so the
        producer thread is not disrupted.
        """
        websocket = self._connections.get(attack_id)
        if websocket is None:
            logger.warning("No WebSocket for attack_id=%s — dropping message", attack_id)
            return
        try:
            await websocket.send_json(message)
        except WebSocketDisconnect:
            logger.info("Client disconnected during send for attack_id=%s", attack_id)
        except Exception:
            logger.exception("Unexpected error sending to attack_id=%s", attack_id)

    async def broadcast(self, message: dict) -> None:
        """Send a JSON message to every connected client."""
        disconnected: list[str] = []
        for attack_id, websocket in self._connections.items():
            try:
                await websocket.send_json(message)
            except WebSocketDisconnect:
                disconnected.append(attack_id)
            except Exception:
                logger.exception("Error broadcasting to attack_id=%s", attack_id)
                disconnected.append(attack_id)
        # Clean up any connections that died during broadcast
        for aid in disconnected:
            self._connections.pop(aid, None)
