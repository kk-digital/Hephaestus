"""Workflow routes for Hephaestus MCP server."""

import logging
from fastapi import APIRouter, HTTPException, Header

from src.c1_workflow_models.workflow import Workflow
from src.c2_workflow_result_service.result_service import WorkflowResultService

logger = logging.getLogger(__name__)


def create_workflow_router(server_state):
    """Create workflow router with server_state dependency.

    Args:
        server_state: ServerState instance with db_manager

    Returns:
        APIRouter: Configured router with workflow endpoints
    """
    router = APIRouter(tags=["workflows"])

    @router.get("/workflows/{workflow_id}/results")
    async def get_workflow_results(
        workflow_id: str,
        requesting_agent_id: str = Header(None, alias="X-Agent-ID"),
    ):
        """Get all results for a specific workflow."""
        try:
            results = WorkflowResultService.get_workflow_results(workflow_id)
            return results
        except Exception as e:
            logger.error(f"Failed to get workflow results: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @router.get("/api/workflows")
    async def get_workflows_endpoint(
        agent_id: str = Header(..., alias="X-Agent-ID"),
    ):
        """Get all workflows."""
        logger.info(f"Agent {agent_id} fetching workflows")

        try:
            session = server_state.db_manager.get_session()
            try:
                workflows = session.query(Workflow).all()

                return [
                    {
                        "id": w.id,
                        "name": w.name,
                        "status": w.status,
                        "phases_folder_path": w.phases_folder_path,
                        "created_at": w.created_at.isoformat() if w.created_at else None,
                    }
                    for w in workflows
                ]
            finally:
                session.close()

        except Exception as e:
            logger.error(f"Failed to fetch workflows: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    return router
