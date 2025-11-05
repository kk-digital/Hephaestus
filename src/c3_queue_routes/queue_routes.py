"""Queue status routes for Hephaestus MCP server."""

import logging
from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)


def create_queue_router(server_state):
    """Create queue router with server_state dependency.

    Args:
        server_state: ServerState instance with queue_service

    Returns:
        APIRouter: Configured router with queue endpoints
    """
    router = APIRouter(tags=["queue"])

    @router.get("/api/queue_status")
    async def get_queue_status_endpoint():
        """Get current queue status information.

        Returns information about active agents, queued tasks, and available slots.
        """
        try:
            status = server_state.queue_service.get_queue_status()
            return status
        except Exception as e:
            logger.error(f"Failed to get queue status: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    return router
