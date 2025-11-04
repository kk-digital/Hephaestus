"""Agent management routes for Hephaestus MCP server."""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Header, Body

from src.c1_agent_models.agent import Agent
from src.c1_task_models.task import Task

logger = logging.getLogger(__name__)


def create_agent_router(server_state, process_queue):
    """Create agent router with server_state dependency.

    Args:
        server_state: ServerState instance with db_manager, agent_manager
        process_queue: Async function to process task queue

    Returns:
        APIRouter: Configured router with agent endpoints
    """
    router = APIRouter(tags=["agents"])

    @router.post("/api/terminate_agent")
    async def terminate_agent_endpoint(
        agent_id: str = Body(..., embed=True),
        reason: str = Body(default="Manual termination", embed=True),
    ):
        """Manually terminate an agent from the UI.

        This endpoint allows users to forcefully terminate running agents.
        After termination, the queue is processed to start the next queued task if any.
        """
        logger.info(f"Manual termination request for agent {agent_id}: {reason}")

        try:
            session = server_state.db_manager.get_session()
            try:
                # Verify agent exists
                agent = session.query(Agent).filter_by(id=agent_id).first()
                if not agent:
                    raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")

                if agent.status == "terminated":
                    raise HTTPException(status_code=400, detail=f"Agent {agent_id} is already terminated")

                # Get the agent's task if any
                task = None
                if agent.current_task_id:
                    task = session.query(Task).filter_by(id=agent.current_task_id).first()

                # Terminate the agent and mark task as failed
                await server_state.agent_manager.terminate_agent(agent_id)

                if task:
                    task.status = "failed"
                    task.failure_reason = f"Manually terminated: {reason}"
                    task.completed_at = datetime.utcnow()
                    session.commit()

            finally:
                session.close()

            # Process queue after termination
            await process_queue()

            # Broadcast update
            await server_state.broadcast_update({
                "type": "agent_terminated_manually",
                "agent_id": agent_id,
                "reason": reason,
            })

            logger.info(f"Agent {agent_id} terminated successfully")

            return {
                "success": True,
                "message": f"Agent {agent_id[:8]} terminated successfully",
                "reason": reason,
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to terminate agent: {e}")
            import traceback
            logger.error(traceback.format_exc())
            raise HTTPException(status_code=500, detail=str(e))

    @router.get("/agent_status")
    async def get_agent_status(
        agent_id: str = Header(..., alias="X-Agent-ID"),
    ):
        """Get current agent status including task, phase, and progress information."""
        try:
            session = server_state.db_manager.get_session()

            agent = session.query(Agent).filter_by(id=agent_id).first()
            if not agent:
                raise HTTPException(status_code=404, detail="Agent not found")

            # Get current task if any
            task_info = None
            if agent.current_task_id:
                task = session.query(Task).filter_by(id=agent.current_task_id).first()
                if task:
                    task_info = {
                        "id": task.id,
                        "status": task.status,
                        "description": task.enriched_description or task.raw_description,
                        "phase_id": task.phase_id,
                        "workflow_id": task.workflow_id,
                    }

            # Build response
            response = {
                "agent_id": agent.id,
                "status": agent.status,
                "current_task": task_info,
                "workflow_id": agent.workflow_id,
                "created_at": agent.created_at.isoformat() if agent.created_at else None,
            }

            session.close()
            return response

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to get agent status: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @router.get("/task_progress")
    async def get_task_progress(
        task_id: Optional[str] = None,
        agent_id: str = Header(..., alias="X-Agent-ID"),
    ):
        """Get progress information for a task or all tasks for an agent."""
        try:
            session = server_state.db_manager.get_session()

            if task_id:
                # Get specific task
                task = session.query(Task).filter_by(id=task_id).first()
                if not task:
                    raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

                tasks = [task]
            else:
                # Get all tasks for this agent
                tasks = session.query(Task).filter_by(created_by_agent_id=agent_id).all()

            result = []
            for task in tasks:
                task_data = {
                    "id": task.id,
                    "status": task.status,
                    "description": task.enriched_description or task.raw_description,
                    "assigned_agent_id": task.assigned_agent_id,
                    "priority": task.priority,
                    "started_at": task.started_at.isoformat() if task.started_at else None,
                    "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                    "failure_reason": task.failure_reason,
                    "validation_enabled": task.validation_enabled,
                }
                result.append(task_data)

            session.close()
            return result

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to get task progress: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    return router
