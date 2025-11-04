"""Memory and results routes for Hephaestus MCP server."""

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel, Field

from src.c1_memory_models.memory import Memory
from src.c1_task_models.task import Task
from src.c1_workflow_models.workflow import Workflow, Phase
from src.c1_agent_models.agent import Agent, AgentResult
from src.c2_result_service.result_service import ResultService
from src.c2_workflow_result_service.result_service import WorkflowResultService
from src.c2_validation_service.result_validator_service import ResultValidatorService

logger = logging.getLogger(__name__)


# Request/Response Models
class SaveMemoryRequest(BaseModel):
    """Request model for saving memory."""

    ai_agent_id: str
    memory_content: str
    memory_type: str = Field(
        ...,
        pattern="^(error_fix|discovery|decision|learning|warning|codebase_knowledge)$"
    )
    related_files: Optional[List[str]] = Field(default=None)
    tags: Optional[List[str]] = Field(default=None)


class SaveMemoryResponse(BaseModel):
    """Response model for memory saving."""

    memory_id: str
    indexed: bool
    similar_memories: Optional[List[str]] = Field(default=None)


class ReportResultsRequest(BaseModel):
    """Request model for reporting task results."""

    task_id: str = Field(..., description="ID of the task")
    markdown_file_path: str = Field(..., description="Path to markdown file with results")
    result_type: str = Field(
        ...,
        pattern="^(implementation|analysis|fix|design|test|documentation)$",
        description="Type of result"
    )
    summary: str = Field(..., description="Brief summary of the result")


class ReportResultsResponse(BaseModel):
    """Response model for result reporting."""

    status: str = Field(..., description="stored or error")
    result_id: str = Field(..., description="ID of the stored result")
    task_id: str = Field(..., description="ID of the task")
    agent_id: str = Field(..., description="ID of the agent")
    verification_status: str = Field(..., description="Verification status")
    created_at: str = Field(..., description="ISO timestamp of creation")


class GiveValidationReviewRequest(BaseModel):
    """Request model for validation review submission."""

    task_id: str = Field(..., description="ID of task being validated")
    validator_agent_id: str = Field(..., description="ID of validator agent")
    validation_passed: bool = Field(..., description="Whether validation passed")
    feedback: str = Field(..., description="Detailed feedback")
    evidence: List[Dict[str, Any]] = Field(default_factory=list, description="Evidence supporting decision")
    recommendations: List[str] = Field(default_factory=list, description="Follow-up task recommendations")


class GiveValidationReviewResponse(BaseModel):
    """Response model for validation review."""

    status: str = Field(..., description="completed, needs_work, or error")
    message: str = Field(..., description="Status message")
    iteration: Optional[int] = Field(default=None, description="Current iteration number")


class SubmitResultRequest(BaseModel):
    """Request model for submitting workflow results."""

    markdown_file_path: str = Field(..., description="Path to markdown file with result evidence")
    explanation: str = Field(..., description="Brief explanation of what was accomplished")
    evidence: Optional[List[str]] = Field(default=None, description="List of evidence supporting completion")


class SubmitResultResponse(BaseModel):
    """Response model for result submission."""

    status: str = Field(..., description="submitted, rejected, or error")
    result_id: Optional[str] = Field(default=None, description="ID of the submitted result")
    workflow_id: str = Field(..., description="ID of the workflow")
    agent_id: str = Field(..., description="ID of the agent")
    validation_triggered: bool = Field(..., description="Whether validation was triggered")
    message: str = Field(..., description="Status message")
    created_at: Optional[str] = Field(default=None, description="ISO timestamp of creation")


class SubmitResultValidationRequest(BaseModel):
    """Request model for result validation submission."""

    result_id: str = Field(..., description="ID of result being validated")
    validation_passed: bool = Field(..., description="Whether validation passed")
    feedback: str = Field(..., description="Detailed validation feedback")
    evidence: List[Dict[str, Any]] = Field(default_factory=list, description="Evidence supporting decision")


class SubmitResultValidationResponse(BaseModel):
    """Response model for result validation."""

    status: str = Field(..., description="completed, workflow_terminated, or error")
    message: str = Field(..., description="Status message")
    workflow_action_taken: Optional[str] = Field(default=None, description="Action taken on workflow")
    result_id: str = Field(..., description="ID of the validated result")


def create_memory_router(server_state):
    """Create memory router with server_state dependency.

    Args:
        server_state: ServerState instance with db_manager, vector_store, etc.

    Returns:
        APIRouter: Configured router with memory/results endpoints
    """
    router = APIRouter(tags=["memory", "results"])

    @router.post("/save_memory", response_model=SaveMemoryResponse)
    async def save_memory(
        request: SaveMemoryRequest,
        agent_id: str = Header(..., alias="X-Agent-ID"),
    ):
        """Store important discoveries and learnings."""
        logger.info(f"Saving memory from agent {agent_id}: {request.memory_content[:100]}...")

        try:
            # Generate memory ID immediately
            memory_id = str(uuid.uuid4())

            # Create initial memory record in database
            session = server_state.db_manager.get_session()
            memory = Memory(
                id=memory_id,
                agent_id=agent_id,
                content=request.memory_content,
                memory_type=request.memory_type,
                embedding_id=None,  # Will be updated after processing
                tags=request.tags,
                related_files=request.related_files,
            )
            session.add(memory)
            session.commit()
            session.close()

            # Process the embedding and deduplication asynchronously
            async def process_memory_async():
                try:
                    # 1. Generate embedding
                    embedding = await server_state.llm_provider.generate_embedding(request.memory_content)

                    # 2. Check for similar memories
                    similar = await server_state.vector_store.search(
                        collection="agent_memories",
                        query_vector=embedding,
                        limit=5,
                        score_threshold=0.95,  # High threshold for deduplication
                    )

                    # 3. If not duplicate, store in vector database
                    if not similar or similar[0]["score"] < 0.95:
                        # Store in vector database
                        success = await server_state.vector_store.store_memory(
                            collection="agent_memories",
                            memory_id=memory_id,
                            embedding=embedding,
                            content=request.memory_content,
                            metadata={
                                "agent_id": agent_id,
                                "memory_type": request.memory_type,
                                "related_files": request.related_files,
                                "tags": request.tags,
                            },
                        )

                        # Update memory with embedding ID
                        session = server_state.db_manager.get_session()
                        memory = session.query(Memory).filter_by(id=memory_id).first()
                        if memory:
                            memory.embedding_id = memory_id if success else None
                            session.commit()
                        session.close()

                        logger.info(f"Memory {memory_id} indexed successfully in background")
                    else:
                        # Memory is too similar to existing one - mark as duplicate
                        session = server_state.db_manager.get_session()
                        memory = session.query(Memory).filter_by(id=memory_id).first()
                        if memory:
                            # Mark as duplicate by adding a reference to the original
                            memory.tags = (memory.tags or []) + [f"duplicate_of:{similar[0]['id']}"]
                            session.commit()
                        session.close()
                        logger.info(f"Memory {memory_id} marked as duplicate of {similar[0]['id']}")

                except Exception as e:
                    logger.error(f"Failed to process memory {memory_id} in background: {e}")
                    # Update memory with error status
                    session = server_state.db_manager.get_session()
                    memory = session.query(Memory).filter_by(id=memory_id).first()
                    if memory:
                        memory.tags = (memory.tags or []) + [f"indexing_error:{str(e)[:50]}"]
                        session.commit()
                    session.close()

            # Start background processing
            asyncio.create_task(process_memory_async())

            # Return immediately with memory ID
            return SaveMemoryResponse(
                memory_id=memory_id,
                indexed=True,  # Optimistically return true (indexing happens async)
                similar_memories=None,  # Can't provide this synchronously anymore
            )

        except Exception as e:
            logger.error(f"Failed to save memory: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @router.post("/report_results", response_model=ReportResultsResponse)
    async def report_results(
        request: ReportResultsRequest,
        agent_id: str = Header(..., alias="X-Agent-ID"),
    ):
        """Report task results with markdown file."""
        logger.info(f"Agent {agent_id} reporting results for task {request.task_id}")

        try:
            # Mark task as having results
            session = server_state.db_manager.get_session()
            task = session.query(Task).filter_by(id=request.task_id).first()
            if task:
                task.has_results = True
                session.commit()
            session.close()

            # Store the result
            result = await ResultService.create_result(
                task_id=request.task_id,
                agent_id=agent_id,
                result_type=request.result_type,
                markdown_file_path=request.markdown_file_path,
                summary=request.summary,
            )

            return ReportResultsResponse(
                status="stored",
                result_id=result.id,
                task_id=request.task_id,
                agent_id=agent_id,
                verification_status="pending",
                created_at=result.created_at.isoformat(),
            )

        except Exception as e:
            logger.error(f"Failed to report results: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @router.post("/give_validation_review", response_model=GiveValidationReviewResponse)
    async def give_validation_review(
        request: GiveValidationReviewRequest,
        agent_id: str = Header(..., alias="X-Agent-ID"),
    ):
        """Submit validation review for a task."""
        logger.info(f"Validator {request.validator_agent_id} reviewing task {request.task_id}: {'PASSED' if request.validation_passed else 'FAILED'}")

        try:
            session = server_state.db_manager.get_session()

            # Get task and verify it's under review or in validation
            task = session.query(Task).filter_by(id=request.task_id).first()
            if not task:
                raise HTTPException(status_code=404, detail="Task not found")

            if task.status not in ["under_review", "validation_in_progress"]:
                raise HTTPException(
                    status_code=400,
                    detail=f"Task is not under validation (status: {task.status})"
                )

            # Get original agent
            original_agent = session.query(Agent).filter_by(id=task.assigned_agent_id).first()

            if request.validation_passed:
                # Validation passed - mark task complete
                task.status = "done"
                task.completed_at = datetime.utcnow()
                task.validation_feedback = request.feedback
                session.commit()

                # Merge validated work to parent (if worktree manager available)
                merge_commit_sha = None
                if hasattr(server_state, 'worktree_manager') and original_agent:
                    try:
                        merge_result = server_state.worktree_manager.merge_to_parent(original_agent.id)
                        merge_commit_sha = merge_result.get("commit_sha") if isinstance(merge_result, dict) else None
                        logger.info(f"Merged validated work to parent: {merge_result}")
                    except Exception as e:
                        logger.warning(f"Failed to merge validated work to parent: {e}")

                # Auto-link commit to ticket if task has ticket_id
                if task.ticket_id and merge_commit_sha:
                    try:
                        from src.c2_ticket_service.ticket_service import TicketService
                        logger.info(f"Auto-linking validated commit {merge_commit_sha} to ticket {task.ticket_id}")

                        await TicketService.link_commit(
                            ticket_id=task.ticket_id,
                            agent_id=task.assigned_agent_id,
                            commit_sha=merge_commit_sha,
                            commit_message=f"Task {request.task_id} validated and merged",
                            link_method="auto_validation_pass"
                        )

                        logger.info(f"Validated commit {merge_commit_sha} linked to ticket {task.ticket_id}")
                    except Exception as e:
                        logger.error(f"Failed to auto-link validated commit to ticket: {e}")

                # Terminate both original agent and validator
                if original_agent:
                    await server_state.agent_manager.terminate_agent(original_agent.id)
                await server_state.agent_manager.terminate_agent(request.validator_agent_id)

                session.close()

                # Broadcast validation passed
                await server_state.broadcast_update({
                    "type": "validation_passed",
                    "task_id": request.task_id,
                    "validator_id": request.validator_agent_id,
                    "original_agent_id": task.assigned_agent_id,
                })

                return GiveValidationReviewResponse(
                    status="completed",
                    message="Validation passed. Task marked complete.",
                    iteration=task.validation_iteration,
                )

            else:
                # Validation failed - send back for rework
                task.status = "assigned"  # Back to working state
                task.validation_feedback = request.feedback
                session.commit()
                session.close()

                # Send feedback to original agent (via message system)
                if original_agent:
                    await server_state.agent_manager.send_direct_message(
                        sender_agent_id=request.validator_agent_id,
                        recipient_agent_id=original_agent.id,
                        message=f"Validation feedback:\n{request.feedback}\n\nRecommendations:\n" + "\n".join(f"- {rec}" for rec in request.recommendations)
                    )

                # Terminate validator agent
                await server_state.agent_manager.terminate_agent(request.validator_agent_id)

                # Broadcast validation failed
                await server_state.broadcast_update({
                    "type": "validation_failed",
                    "task_id": request.task_id,
                    "validator_id": request.validator_agent_id,
                    "original_agent_id": task.assigned_agent_id,
                })

                return GiveValidationReviewResponse(
                    status="needs_work",
                    message="Validation failed. Task returned for rework.",
                    iteration=task.validation_iteration,
                )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to process validation review: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @router.post("/submit_result", response_model=SubmitResultResponse)
    async def submit_result(
        request: SubmitResultRequest,
        agent_id: str = Header(..., alias="X-Agent-ID"),
    ):
        """Submit workflow result (proof of work completion)."""
        logger.info(f"Agent {agent_id} submitting workflow result")

        try:
            # Get agent's current workflow
            session = server_state.db_manager.get_session()
            agent = session.query(Agent).filter_by(id=agent_id).first()
            if not agent or not agent.workflow_id:
                raise HTTPException(status_code=400, detail="No active workflow for this agent")

            workflow_id = agent.workflow_id
            session.close()

            # Store the workflow result
            result = await WorkflowResultService.create_result(
                workflow_id=workflow_id,
                agent_id=agent_id,
                markdown_file_path=request.markdown_file_path,
                explanation=request.explanation,
                evidence=request.evidence,
            )

            # Check if workflow requires validation
            session = server_state.db_manager.get_session()
            workflow = session.query(Workflow).filter_by(id=workflow_id).first()
            validation_triggered = False

            if workflow and workflow.validation_enabled:
                # Trigger validation
                validation_triggered = True
                # TODO: Spawn validator agent
                logger.info(f"Validation enabled for workflow {workflow_id} - would spawn validator here")

            session.close()

            # Broadcast update
            await server_state.broadcast_update({
                "type": "workflow_result_submitted",
                "workflow_id": workflow_id,
                "agent_id": agent_id,
                "result_id": result.id,
                "validation_triggered": validation_triggered,
            })

            return SubmitResultResponse(
                status="submitted",
                result_id=result.id,
                workflow_id=workflow_id,
                agent_id=agent_id,
                validation_triggered=validation_triggered,
                message="Result submitted successfully",
                created_at=result.created_at.isoformat(),
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to submit result: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @router.post("/submit_result_validation", response_model=SubmitResultValidationResponse)
    async def submit_result_validation(
        request: SubmitResultValidationRequest,
        agent_id: str = Header(..., alias="X-Agent-ID"),
    ):
        """Submit validation of a workflow result."""
        logger.info(f"Validator {agent_id} validating result {request.result_id}: {'PASSED' if request.validation_passed else 'FAILED'}")

        try:
            # Get the result and workflow
            session = server_state.db_manager.get_session()
            result = await WorkflowResultService.get_result(request.result_id)

            if not result:
                raise HTTPException(status_code=404, detail="Result not found")

            workflow_id = result.workflow_id
            original_agent_id = result.agent_id

            if request.validation_passed:
                # Validation passed - update result status
                await WorkflowResultService.update_result_status(
                    result_id=request.result_id,
                    status="validated",
                    validation_feedback=request.feedback,
                )

                # Terminate both agents
                await server_state.agent_manager.terminate_agent(original_agent_id)
                await server_state.agent_manager.terminate_agent(agent_id)

                session.close()

                # Broadcast validation passed
                await server_state.broadcast_update({
                    "type": "result_validation_passed",
                    "result_id": request.result_id,
                    "workflow_id": workflow_id,
                    "validator_id": agent_id,
                })

                return SubmitResultValidationResponse(
                    status="completed",
                    message="Validation passed. Result accepted.",
                    workflow_action_taken="terminated",
                    result_id=request.result_id,
                )

            else:
                # Validation failed - update result and workflow
                await WorkflowResultService.update_result_status(
                    result_id=request.result_id,
                    status="rejected",
                    validation_feedback=request.feedback,
                )

                # Send feedback to original agent
                await server_state.agent_manager.send_direct_message(
                    sender_agent_id=agent_id,
                    recipient_agent_id=original_agent_id,
                    message=f"Result validation failed:\n{request.feedback}"
                )

                # Terminate validator, keep original agent running
                await server_state.agent_manager.terminate_agent(agent_id)

                session.close()

                # Broadcast validation failed
                await server_state.broadcast_update({
                    "type": "result_validation_failed",
                    "result_id": request.result_id,
                    "workflow_id": workflow_id,
                    "validator_id": agent_id,
                })

                return SubmitResultValidationResponse(
                    status="completed",
                    message="Validation failed. Result rejected.",
                    workflow_action_taken="continued",
                    result_id=request.result_id,
                )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to process result validation: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    return router
