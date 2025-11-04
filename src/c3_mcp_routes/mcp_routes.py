"""MCP protocol routes for Claude integration."""

import json
import logging
import asyncio
from typing import Dict, Any
from datetime import datetime

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from src.c1_task_models.task import Task

logger = logging.getLogger(__name__)


def create_mcp_router(server_state):
    """Create MCP router with server_state dependency.

    Args:
        server_state: ServerState instance with db_manager, sse_queues

    Returns:
        APIRouter: Configured router with MCP protocol endpoints
    """
    router = APIRouter(tags=["mcp"])

    @router.get("/tools")
    async def list_tools():
        """List available MCP tools."""
        return {
            "tools": [
                {
                    "name": "create_task",
                    "description": "Create a new task for an autonomous agent",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "task_description": {"type": "string"},
                            "done_definition": {"type": "string"},
                            "priority": {"type": "string", "enum": ["low", "medium", "high"]}
                        },
                        "required": ["task_description", "done_definition"]
                    }
                },
                {
                    "name": "save_memory",
                    "description": "Save a memory to the knowledge base",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "content": {"type": "string"},
                            "memory_type": {"type": "string"},
                            "tags": {"type": "array", "items": {"type": "string"}}
                        },
                        "required": ["content", "memory_type"]
                    }
                },
                {
                    "name": "get_task_status",
                    "description": "Get status of all tasks",
                    "input_schema": {
                        "type": "object",
                        "properties": {}
                    }
                }
            ]
        }

    @router.post("/tools/execute")
    async def execute_tool(request: Dict[str, Any]):
        """Execute an MCP tool."""
        tool_name = request.get("tool")
        arguments = request.get("arguments", {})

        # Import endpoints locally to avoid circular dependencies
        from src.c3_task_routes.task_routes import CreateTaskRequest
        from src.c3_memory_routes.memory_routes import SaveMemoryRequest

        if tool_name == "create_task":
            # Forward to create_task endpoint - need to call the actual endpoint
            # This is a simplified version; full implementation would call the route handler
            raise HTTPException(status_code=501, detail="MCP tool execution not fully implemented")
        elif tool_name == "save_memory":
            # Forward to save_memory endpoint
            raise HTTPException(status_code=501, detail="MCP tool execution not fully implemented")
        elif tool_name == "get_task_status":
            # Return task progress
            raise HTTPException(status_code=501, detail="MCP tool execution not fully implemented")
        else:
            raise HTTPException(status_code=400, detail=f"Unknown tool: {tool_name}")

    @router.get("/resources")
    async def list_resources():
        """List available MCP resources."""
        session = server_state.db_manager.get_session()
        try:
            tasks = session.query(Task).filter(Task.status != "done").all()
            return {
                "resources": [
                    {
                        "uri": f"task://{task.id}",
                        "name": f"Task: {task.id[:8]}",
                        "description": (task.enriched_description or task.raw_description)[:100],
                        "mimeType": "application/json"
                    }
                    for task in tasks
                ]
            }
        finally:
            session.close()

    @router.get("/resources/{resource_uri:path}")
    async def get_resource(resource_uri: str):
        """Get a specific MCP resource."""
        if resource_uri.startswith("task://"):
            task_id = resource_uri.replace("task://", "")
            session = server_state.db_manager.get_session()
            try:
                task = session.query(Task).filter_by(id=task_id).first()
                if task:
                    return {
                        "uri": resource_uri,
                        "content": {
                            "id": task.id,
                            "description": task.enriched_description or task.raw_description,
                            "status": task.status,
                            "assigned_agent": task.assigned_agent_id,
                            "created_at": task.created_at.isoformat() if task.created_at else None
                        }
                    }
                else:
                    raise HTTPException(status_code=404, detail="Task not found")
            finally:
                session.close()
        else:
            raise HTTPException(status_code=404, detail="Resource not found")

    @router.get("/sse")
    async def sse_endpoint():
        """Server-Sent Events endpoint for Claude MCP integration."""
        async def event_generator():
            """Generate SSE events."""
            # Send initial connection event
            yield f"data: {json.dumps({'type': 'connected', 'message': 'Connected to Hephaestus MCP Server', 'timestamp': datetime.utcnow().isoformat()})}\n\n"

            # Create a queue for this SSE connection
            event_queue = asyncio.Queue(maxsize=100)
            server_state.sse_queues.append(event_queue)

            try:
                while True:
                    # Wait for events to send
                    try:
                        # Check for events with timeout to send keepalive
                        event = await asyncio.wait_for(event_queue.get(), timeout=30.0)
                        yield f"data: {json.dumps(event)}\n\n"
                    except asyncio.TimeoutError:
                        # Send keepalive event every 30 seconds
                        yield f"data: {json.dumps({'type': 'keepalive', 'timestamp': datetime.utcnow().isoformat()})}\n\n"
            except asyncio.CancelledError:
                # Clean up when connection is closed
                if event_queue in server_state.sse_queues:
                    server_state.sse_queues.remove(event_queue)
                raise
            finally:
                # Ensure cleanup
                if event_queue in server_state.sse_queues:
                    server_state.sse_queues.remove(event_queue)

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    return router
