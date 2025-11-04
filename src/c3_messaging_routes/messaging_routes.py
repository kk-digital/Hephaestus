"""Agent messaging routes for Hephaestus MCP server."""

import logging
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# Request/Response Models
class BroadcastMessageRequest(BaseModel):
    """Request model for broadcasting a message to all agents."""

    message: str = Field(..., description="Message content to broadcast")


class BroadcastMessageResponse(BaseModel):
    """Response model for message broadcast."""

    success: bool = Field(..., description="Whether broadcast was successful")
    recipient_count: int = Field(..., description="Number of agents message was sent to")
    message: str = Field(..., description="Status message")


class SendMessageRequest(BaseModel):
    """Request model for sending a direct message to an agent."""

    recipient_agent_id: str = Field(..., description="ID of the agent to send message to")
    message: str = Field(..., description="Message content")


class SendMessageResponse(BaseModel):
    """Response model for direct message."""

    success: bool = Field(..., description="Whether message was sent successfully")
    message: str = Field(..., description="Status message")


def create_messaging_router(server_state):
    """Create messaging router with server_state dependency.

    Args:
        server_state: ServerState instance with agent_manager and broadcast_update

    Returns:
        APIRouter: Configured router with messaging endpoints
    """
    router = APIRouter(tags=["messaging"])

    @router.post("/api/broadcast_message", response_model=BroadcastMessageResponse)
    async def broadcast_message(
        request: BroadcastMessageRequest,
        agent_id: str = Header(..., alias="X-Agent-ID"),
    ):
        """Broadcast a message to all active agents except the sender.

        This allows agents to communicate with each other by sending messages
        that will be delivered to all other active agents in the system.
        """
        logger.info(f"Agent {agent_id[:8]} broadcasting message: {request.message[:100]}...")

        try:
            # Use agent manager to broadcast the message
            recipient_count = await server_state.agent_manager.broadcast_message_to_all_agents(
                sender_agent_id=agent_id,
                message=request.message
            )

            # Broadcast update via WebSocket
            await server_state.broadcast_update({
                "type": "agent_broadcast",
                "sender_agent_id": agent_id,
                "recipient_count": recipient_count,
                "message_preview": request.message[:100],
            })

            return BroadcastMessageResponse(
                success=True,
                recipient_count=recipient_count,
                message=f"Message broadcast to {recipient_count} agent(s)"
            )

        except Exception as e:
            logger.error(f"Failed to broadcast message: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @router.post("/api/send_message", response_model=SendMessageResponse)
    async def send_message(
        request: SendMessageRequest,
        agent_id: str = Header(..., alias="X-Agent-ID"),
    ):
        """Send a direct message to a specific agent.

        This allows agents to communicate directly with each other by sending
        targeted messages to specific agents.
        """
        logger.info(f"Agent {agent_id[:8]} sending message to {request.recipient_agent_id[:8]}: {request.message[:100]}...")

        try:
            # Use agent manager to send the direct message
            success = await server_state.agent_manager.send_direct_message(
                sender_agent_id=agent_id,
                recipient_agent_id=request.recipient_agent_id,
                message=request.message
            )

            if not success:
                return SendMessageResponse(
                    success=False,
                    message=f"Failed to send message - recipient agent {request.recipient_agent_id[:8]} may not exist or is terminated"
                )

            # Broadcast update via WebSocket
            await server_state.broadcast_update({
                "type": "agent_direct_message",
                "sender_agent_id": agent_id,
                "recipient_agent_id": request.recipient_agent_id,
                "message_preview": request.message[:100],
            })

            return SendMessageResponse(
                success=True,
                message=f"Message sent to agent {request.recipient_agent_id[:8]}"
            )

        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    return router
