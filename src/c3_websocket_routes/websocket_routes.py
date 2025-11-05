"""WebSocket routes for Hephaestus MCP server."""

import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


def create_websocket_router(server_state):
    """Create WebSocket router with server_state dependency.

    Args:
        server_state: ServerState instance with active_websockets list

    Returns:
        APIRouter: Configured router with WebSocket endpoint
    """
    router = APIRouter(tags=["websocket"])

    @router.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        """WebSocket endpoint for real-time updates."""
        await websocket.accept()
        server_state.active_websockets.append(websocket)

        try:
            while True:
                # Keep connection alive and handle any incoming messages
                data = await websocket.receive_text()
                # Echo back or handle commands
                await websocket.send_json({"type": "echo", "data": data})

        except WebSocketDisconnect:
            server_state.active_websockets.remove(websocket)
            logger.info("WebSocket client disconnected")

    return router
