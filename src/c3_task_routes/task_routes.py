"""Task management routes for Hephaestus MCP server."""

import asyncio
import logging
import os
import re
import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Header, Body
from pydantic import BaseModel, Field

from src.core.simple_config import get_config
from src.c1_task_models.task import Task
from src.c1_agent_models.agent import Agent
from src.c1_workflow_models.workflow import Phase
from src.c1_memory_models.memory import Memory
from src.c2_task_similarity_service.similarity_service import TaskSimilarityService
from src.c2_task_blocking_service.blocking_service import TaskBlockingService
from src.c2_ticket_service.ticket_service import TicketService

logger = logging.getLogger(__name__)


# Request/Response Models
class CreateTaskRequest(BaseModel):
    """Request model for creating a task."""

    task_description: str = Field(..., description="Raw task description")
    done_definition: str = Field(..., description="What constitutes completion")
    ai_agent_id: str = Field(..., description="ID of requesting agent")
    priority: Optional[str] = Field(default="medium", pattern="^(low|medium|high)$")
    parent_task_id: Optional[str] = Field(default=None, description="Parent task ID for sub-tasks")
    phase_id: Optional[str] = Field(default=None, description="Phase ID for workflow-based tasks")
    phase_order: Optional[int] = Field(default=None, description="Phase order number (alternative to phase_id)")
    cwd: Optional[str] = Field(default=None, description="Working directory for the task")
    ticket_id: Optional[str] = Field(default=None, description="Associated ticket ID (required when ticket tracking enabled)")


class CreateTaskResponse(BaseModel):
    """Response model for task creation."""

    task_id: str
    enriched_description: str
    assigned_agent_id: str
    estimated_completion_time: int  # minutes
    status: str


class UpdateTaskStatusRequest(BaseModel):
    """Request model for updating task status."""

    task_id: str
    status: str = Field(..., pattern="^(done|failed)$")
    summary: str = Field(..., description="What was accomplished")
    key_learnings: List[str] = Field(..., description="Important discoveries")
    code_changes: Optional[List[str]] = Field(default=None, description="Files modified/created")
    failure_reason: Optional[str] = Field(default=None, description="Required if status is 'failed'")


class UpdateTaskStatusResponse(BaseModel):
    """Response model for task status update."""

    success: bool
    message: str
    termination_scheduled: bool


def create_task_router(server_state, process_queue):
    """Create task router with server_state dependency.

    Args:
        server_state: ServerState instance with db_manager, agent_manager, etc.
        process_queue: Async function to process task queue

    Returns:
        APIRouter: Configured router with task endpoints
    """
    router = APIRouter(tags=["tasks"])

    @router.post("/create_task", response_model=CreateTaskResponse)
    async def create_task(
        request: CreateTaskRequest,
        agent_id: str = Header(..., alias="X-Agent-ID"),
    ):
        """Create a new task with automatic enrichment and agent assignment."""
        logger.info(f"Creating task from agent {agent_id}: {request.task_description[:100]}...")

        try:
            # Check if ticket tracking is enabled and ticket_id is required
            # EXCEPTION: SDK agents (main-session-agent or agents with 'sdk'/'main' in ID)
            # can create tasks without ticket_id as they are often the ticket creators

            # Check if ticket tracking is enabled in the system (any board config exists)
            session = server_state.db_manager.get_session()
            try:
                from src.core.database import BoardConfig
                # Check if there are any board configs (indicating ticket tracking is active)
                has_ticket_tracking = session.query(BoardConfig).first() is not None

                # If ticket tracking is enabled globally, require ticket_id from MCP agents
                if has_ticket_tracking and not request.ticket_id:
                    # Check if this is an SDK agent (allowed to create tasks without tickets)
                    is_sdk_agent = (
                        agent_id == "main-session-agent" or
                        "sdk" in agent_id.lower() or
                        "main" in agent_id.lower()
                    )

                    if not is_sdk_agent:
                        session.close()
                        raise HTTPException(
                            status_code=400,
                            detail="Ticket tracking is enabled. MCP agents MUST provide ticket_id. "
                                   "Create a ticket first using create_ticket, then use that ticket_id here. "
                                   "Only SDK/root agents can create tasks without tickets."
                        )
            finally:
                if session.is_active:
                    session.close()

            # Generate task ID immediately
            task_id = str(uuid.uuid4())

            # Create initial task in database with pending status
            session = server_state.db_manager.get_session()
            task = Task(
                id=task_id,
                raw_description=request.task_description,
                enriched_description=f"[Processing] {request.task_description}",  # Placeholder
                done_definition=request.done_definition,
                status="pending",
                priority=request.priority,
                parent_task_id=request.parent_task_id,
                created_by_agent_id=agent_id,
                phase_id=request.phase_id,
                workflow_id=None,
                estimated_complexity=5,  # Default value
                ticket_id=request.ticket_id,  # Store associated ticket ID
            )
            session.add(task)
            session.commit()
            session.close()

            # Check if task's ticket is blocked
            if request.ticket_id:
                blocking_info = TaskBlockingService.check_task_blocked(task_id)

                if blocking_info["is_blocked"]:
                    # Ticket is blocked - mark task as blocked immediately
                    logger.info(
                        f"Task {task_id} associated with blocked ticket {request.ticket_id}. "
                        f"Marking task as 'blocked'. Blocked by: {blocking_info['blocking_ticket_ids']}"
                    )

                    session = server_state.db_manager.get_session()
                    try:
                        task_obj = session.query(Task).filter_by(id=task_id).first()
                        if task_obj:
                            task_obj.status = "blocked"

                            blocker_titles = [t["title"] for t in blocking_info["blocking_tickets"]]
                            task_obj.completion_notes = f"Blocked by tickets: {', '.join(blocker_titles)}"

                            session.commit()
                    finally:
                        session.close()

                    # Broadcast blocked status
                    await server_state.broadcast_update({
                        "type": "task_blocked",
                        "task_id": task_id,
                        "description": request.task_description[:200],
                        "blocking_tickets": blocking_info["blocking_ticket_ids"],
                    })

                    # Return immediately - don't process this task further
                    return {
                        "task_id": task_id,
                        "enriched_description": request.task_description,  # Use raw description for blocked tasks
                        "assigned_agent_id": "none",  # No agent assigned for blocked tasks
                        "estimated_completion_time": 0,  # No estimate for blocked tasks
                        "status": "blocked",
                    }

            # Process the rest asynchronously
            async def process_task_async():
                try:
                    # 1. Determine phase if workflow is active
                    logger.info(f"=== TASK CREATION PHASE DEBUG for task {task_id} ===")
                    logger.info(f"Request phase_id: {request.phase_id}")
                    logger.info(f"Request phase_order: {request.phase_order}")
                    logger.info(f"Server phase_manager: {server_state.phase_manager}")
                    logger.info(f"Server phase_manager.workflow_id: {getattr(server_state.phase_manager, 'workflow_id', 'NOT SET')}")
                    logger.debug(f"Server phase_manager.active_workflow: {getattr(server_state.phase_manager, 'active_workflow', 'NOT SET')}...")

                    # Use the phase_id from the request first, then fallback to phase_manager
                    phase_id = request.phase_id
                    workflow_id = None
                    phase_context_str = ""

                    if server_state.phase_manager.workflow_id:
                        logger.info(f"Workflow is active with ID: {server_state.phase_manager.workflow_id}")

                        # Handle phase identification - request.phase_id might be a phase order number, not UUID
                        if request.phase_id and str(request.phase_id).isdigit():
                            # request.phase_id is actually a phase order number
                            logger.info(f"phase_id appears to be an order number: {request.phase_id}")
                            phase_id = server_state.phase_manager.get_phase_for_task(
                                phase_id=None,
                                order=int(request.phase_id),
                                requesting_agent_id=agent_id
                            )
                            logger.info(f"get_phase_for_task returned phase_id: {phase_id} for order: {request.phase_id}")
                        elif request.phase_id:
                            # request.phase_id is a UUID string
                            logger.info(f"phase_id appears to be a UUID: {request.phase_id}")
                            phase_id = request.phase_id
                        else:
                            # No phase specified, get current phase
                            logger.info(f"No explicit phase_id in request, calling get_phase_for_task")
                            phase_id = server_state.phase_manager.get_phase_for_task(
                                phase_id=None,
                                order=request.phase_order,
                                requesting_agent_id=agent_id
                            )
                            logger.info(f"get_phase_for_task returned: {phase_id}")

                        if phase_id:
                            logger.info(f"Getting phase context for phase_id: {phase_id}")
                            # Get phase context for enrichment
                            phase_context = server_state.phase_manager.get_phase_context(phase_id)
                            logger.debug(f"get_phase_context returned: {phase_context}")
                            if phase_context:
                                logger.info(f"Phase context found, generating prompt context")
                                phase_context_str = phase_context.to_prompt_context()
                                workflow_id = phase_context.workflow_id
                                logger.info(f"Generated context length: {len(phase_context_str)}, workflow_id: {workflow_id}")
                            else:
                                logger.warning(f"No phase context returned for phase_id: {phase_id}")
                        else:
                            logger.warning(f"No phase_id determined for task")
                    else:
                        logger.warning(f"No active workflow in phase_manager")

                    logger.info(f"Final values: phase_id={phase_id}, workflow_id={workflow_id}, context_length={len(phase_context_str)}")
                    logger.info(f"=== END TASK CREATION PHASE DEBUG ===")

                    # 2. Determine working directory (priority: request > phase > server)
                    working_directory = request.cwd  # From request
                    if not working_directory and phase_id:
                        # Get phase working directory
                        session = server_state.db_manager.get_session()
                        phase = session.query(Phase).filter_by(id=phase_id).first()
                        if phase and phase.working_directory:
                            working_directory = phase.working_directory
                        session.close()
                    if not working_directory:
                        working_directory = os.getcwd()  # Server's current directory

                    # 3. Retrieve relevant context from RAG
                    context_memories = await server_state.rag_system.retrieve_for_task(
                        task_description=request.task_description,
                        requesting_agent_id=agent_id,
                    )

                    # 4. Get project context
                    project_context = await server_state.agent_manager.get_project_context()

                    # Add phase context to project context
                    if phase_context_str:
                        project_context = f"{project_context}\n\n{phase_context_str}"

                    # 5. Enrich task using LLM
                    context_strings = [mem.get("content", "") for mem in context_memories]
                    enriched_task = await server_state.llm_provider.enrich_task(
                        task_description=request.task_description,
                        done_definition=request.done_definition,
                        context=context_strings,
                        phase_context=phase_context_str if phase_context_str else None,
                    )

                    # 6. Update task with enriched data
                    session = server_state.db_manager.get_session()
                    task = session.query(Task).filter_by(id=task_id).first()
                    if task:
                        task.enriched_description = enriched_task["enriched_description"]
                        task.phase_id = phase_id
                        task.workflow_id = workflow_id
                        task.estimated_complexity = enriched_task.get("estimated_complexity", 5)

                        # Check if phase has validation enabled and inherit it
                        if phase_id:
                            phase = session.query(Phase).filter_by(id=phase_id).first()
                            if phase and phase.validation:
                                # Check if validation is explicitly disabled
                                if phase.validation.get("enabled", True):  # Default to True if not specified
                                    task.validation_enabled = True
                                    logger.info(f"Task {task_id} inheriting validation from phase {phase.name}")
                                else:
                                    logger.info(f"Task {task_id} validation explicitly disabled in phase {phase.name}")

                        session.commit()

                        # Store task data before closing session
                        task_data = {
                            "id": task_id,
                            "raw_description": request.task_description,
                            "enriched_description": enriched_task["enriched_description"],
                            "done_definition": request.done_definition,
                            "phase_id": phase_id,
                        }
                        session.close()

                        # 6.5 Check for duplicates if deduplication is enabled
                        duplicate_info = None
                        if (server_state.embedding_service and
                            server_state.task_similarity_service and
                            get_config().task_dedup_enabled):

                            try:
                                # Generate embedding for enriched description
                                task_embedding = await server_state.embedding_service.generate_embedding(
                                    enriched_task["enriched_description"]
                                )

                                # Check for duplicates within the same phase
                                duplicate_info = await server_state.task_similarity_service.check_for_duplicates(
                                    enriched_task["enriched_description"],
                                    task_embedding,
                                    phase_id=phase_id  # Only check duplicates within same phase
                                )

                                if duplicate_info['is_duplicate']:
                                    # Update task as duplicate
                                    session = server_state.db_manager.get_session()
                                    task = session.query(Task).filter_by(id=task_id).first()
                                    if task:
                                        task.status = 'duplicated'
                                        task.duplicate_of_task_id = duplicate_info['duplicate_of']
                                        task.similarity_score = duplicate_info['max_similarity']
                                        session.commit()
                                    session.close()

                                    # Log the duplicate detection
                                    logger.warning(
                                        f"Task {task_id} detected as duplicate of {duplicate_info['duplicate_of']} "
                                        f"with similarity {duplicate_info['max_similarity']:.3f}"
                                    )

                                    # Return early (don't create agent for duplicates)
                                    return

                                # Store embedding and related tasks (not a duplicate)
                                await server_state.task_similarity_service.store_task_embedding(
                                    task_id,
                                    task_embedding,
                                    related_tasks_details=duplicate_info.get('related_tasks_details', [])
                                )

                                if duplicate_info.get('related_tasks'):
                                    logger.info(
                                        f"Task {task_id} has {len(duplicate_info['related_tasks'])} related tasks"
                                    )

                            except Exception as e:
                                logger.error(f"Failed to check for duplicates: {e}")
                                # Continue without deduplication on error

                        # 6.5 Check if we should queue the task
                        if server_state.queue_service.should_queue_task():
                            # At capacity - enqueue the task
                            server_state.queue_service.enqueue_task(task_id)

                            # Get queue status for broadcasting
                            queue_status = server_state.queue_service.get_queue_status()

                            # Broadcast queued status
                            await server_state.broadcast_update({
                                "type": "task_queued",
                                "task_id": task_id,
                                "description": enriched_task["enriched_description"][:200],
                                "queue_position": queue_status.get("queued_tasks_count", 0),
                                "slots_available": queue_status.get("slots_available", 0),
                            })

                            logger.info(f"Task {task_id} queued (at capacity: {queue_status['active_agents']}/{queue_status['max_concurrent_agents']} agents)")
                            return  # Don't create agent yet

                        # 7. Create agent for the task (using task data, not the ORM object)
                        # Create a temporary task object for the agent manager
                        logger.info(f"[CREATE_TASK] Creating agent for task {task_id}")
                        logger.info(f"[CREATE_TASK] Task was created by agent: {agent_id}")

                        temp_task = Task(
                            id=task_id,
                            raw_description=task_data["raw_description"],
                            enriched_description=task_data["enriched_description"],
                            done_definition=task_data["done_definition"],
                            phase_id=task_data["phase_id"],
                            created_by_agent_id=agent_id,  # Important: Set the parent agent ID
                        )

                        logger.info(f"[CREATE_TASK] temp_task.created_by_agent_id = {temp_task.created_by_agent_id}")

                        agent = await server_state.agent_manager.create_agent_for_task(
                            task=temp_task,
                            enriched_data=enriched_task,
                            memories=context_memories,
                            project_context=project_context,
                            working_directory=working_directory,
                        )

                        # Store agent ID immediately (before session issues)
                        agent_id_str = str(agent.id) if agent else None

                        # 8. Update task with assigned agent in a new session
                        session = server_state.db_manager.get_session()
                        task = session.query(Task).filter_by(id=task_id).first()
                        if task:
                            task.assigned_agent_id = agent_id_str
                            task.status = "assigned"
                            task.started_at = datetime.utcnow()
                            session.commit()
                        session.close()

                        # 9. Broadcast update via WebSocket
                        await server_state.broadcast_update({
                            "type": "task_created",
                            "task_id": task_id,
                            "agent_id": agent_id_str,
                            "description": enriched_task["enriched_description"][:200],
                        })

                        logger.info(f"Task {task_id} processed successfully in background")
                    else:
                        logger.error(f"Task {task_id} not found after creation")

                except Exception as e:
                    logger.error(f"Failed to process task {task_id} in background: {e}")
                    # Update task status to failed
                    session = server_state.db_manager.get_session()
                    task = session.query(Task).filter_by(id=task_id).first()
                    if task:
                        task.status = "failed"
                        task.failure_reason = str(e)
                        session.commit()
                    session.close()

            # Start processing in the background without waiting
            asyncio.create_task(process_task_async())

            # Return immediately with pending status
            return CreateTaskResponse(
                task_id=task_id,
                enriched_description=f"[Processing] {request.task_description}",
                assigned_agent_id="pending",
                estimated_completion_time=25,
                status="pending",
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to create task: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @router.get("/validate_agent_id/{agent_id}")
    async def validate_agent_id(agent_id: str):
        """Quick endpoint for agents to validate their ID format.

        Returns:
            Success if ID matches UUID format, error otherwise
        """
        uuid_pattern = re.compile(
            r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
            re.IGNORECASE
        )

        if uuid_pattern.match(agent_id):
            return {
                "valid": True,
                "message": f"✅ Agent ID {agent_id} is valid UUID format"
            }
        else:
            return {
                "valid": False,
                "message": f"❌ Agent ID '{agent_id}' is NOT valid. Use the UUID from your initial prompt.",
                "common_mistakes": [
                    "Using 'agent-mcp' instead of actual UUID",
                    "Using 'main-session-agent' when you're not the main session",
                    "Typo in UUID"
                ]
            }

    @router.post("/update_task_status", response_model=UpdateTaskStatusResponse)
    async def update_task_status(
        request: UpdateTaskStatusRequest,
        agent_id: str = Header(..., alias="X-Agent-ID"),
    ):
        """Update task status when complete or failed."""
        logger.info(f"Updating task {request.task_id} status to {request.status}")

        try:
            session = server_state.db_manager.get_session()

            # 1. Verify task exists and agent owns it
            task = session.query(Task).filter_by(id=request.task_id).first()
            if not task:
                raise HTTPException(status_code=404, detail="Task not found")

            if task.assigned_agent_id != agent_id:
                raise HTTPException(status_code=403, detail="Agent not authorized for this task")

            # 2. Save learnings as memories
            for learning in request.key_learnings:
                # Generate embedding
                embedding = await server_state.llm_provider.generate_embedding(learning)

                # Save to vector store
                memory_id = str(uuid.uuid4())
                await server_state.vector_store.store_memory(
                    collection="agent_memories",
                    memory_id=memory_id,
                    embedding=embedding,
                    content=learning,
                    metadata={
                        "agent_id": agent_id,
                        "task_id": request.task_id,
                        "memory_type": "learning",
                        "code_changes": request.code_changes,
                    },
                )

                # Save to database
                memory = Memory(
                    id=memory_id,
                    agent_id=agent_id,
                    content=learning,
                    memory_type="learning",
                    embedding_id=memory_id,
                    related_task_id=request.task_id,
                    related_files=request.code_changes,
                )
                session.add(memory)

            # 3. Check if task has results reported
            if request.status == "done" and not task.has_results:
                logger.warning(f"Task {request.task_id} completed without formal results reported")

            # 4. Check if task has validation enabled
            validation_spawned = False
            if request.status == "done" and task.validation_enabled:
                # Agent claims done but needs validation
                task.status = "under_review"
                task.validation_iteration += 1
                task.completion_notes = request.summary

                # Capture task attributes before async function (to avoid detached instance issues)
                task_validation_iteration = task.validation_iteration
                task_workflow_id = task.workflow_id

                session.commit()

                # Mark original agent as kept alive for validation (do this immediately)
                agent = session.query(Agent).filter_by(id=agent_id).first()
                if agent:
                    agent.kept_alive_for_validation = True
                    session.commit()

                # Process validation spawning asynchronously (like create_task)
                async def spawn_validation_async():
                    try:
                        logger.info(f"Starting validation process for task {request.task_id}")

                        # Commit agent's work for validation (using worktree manager)
                        commit_sha = None
                        if hasattr(server_state, 'worktree_manager'):
                            try:
                                commit_result = server_state.worktree_manager.commit_for_validation(
                                    agent_id=agent_id,
                                    iteration=task_validation_iteration
                                )
                                commit_sha = commit_result.get("commit_sha")
                            except Exception as e:
                                logger.warning(f"Failed to create validation commit: {e}")

                        # Spawn validator agent
                        from src.validation.validator_agent import spawn_validator_agent
                        validator_id = await spawn_validator_agent(
                            validation_type="task",
                            target_id=request.task_id,
                            workflow_id=task_workflow_id,
                            commit_sha=commit_sha or "HEAD",
                            db_manager=server_state.db_manager,
                            worktree_manager=getattr(server_state, 'worktree_manager', None),
                            agent_manager=server_state.agent_manager,
                            original_agent_id=agent_id
                        )

                        # Update task status to validation in progress
                        session = server_state.db_manager.get_session()
                        try:
                            task = session.query(Task).filter_by(id=request.task_id).first()
                            if task:
                                task.status = "validation_in_progress"
                                session.commit()
                                logger.info(f"Task {request.task_id} validation spawned successfully, validator: {validator_id}")
                            else:
                                logger.error(f"Task {request.task_id} not found during validation update")
                        finally:
                            session.close()

                        # Broadcast validation started
                        await server_state.broadcast_update({
                            "type": "validation_started",
                            "task_id": request.task_id,
                            "validator_id": validator_id,
                            "original_agent_id": agent_id,
                        })

                    except Exception as e:
                        logger.error(f"Failed to spawn validation for task {request.task_id}: {e}")
                        # Update task status to failed validation
                        session = server_state.db_manager.get_session()
                        try:
                            task = session.query(Task).filter_by(id=request.task_id).first()
                            if task:
                                task.status = "failed"
                                task.failure_reason = f"Validation spawning failed: {str(e)}"
                                session.commit()

                            # Terminate the agent since validation failed and process queue
                            await server_state.agent_manager.terminate_agent(agent_id)
                            await process_queue()
                        finally:
                            session.close()

                # Start validation process in background
                asyncio.create_task(spawn_validation_async())
                validation_spawned = True

            else:
                # No validation or task failed - proceed normally
                task.status = request.status
                task.completed_at = datetime.utcnow()
                task.completion_notes = request.summary

                if request.status == "failed":
                    task.failure_reason = request.failure_reason

                session.commit()

                # If task completed successfully without validation, merge to parent
                merge_commit_sha = None
                if request.status == "done" and hasattr(server_state, 'worktree_manager'):
                    try:
                        merge_result = server_state.worktree_manager.merge_to_parent(agent_id)
                        merge_commit_sha = merge_result.get("commit_sha") if isinstance(merge_result, dict) else None
                        logger.info(f"Merged completed work to parent (no validation): {merge_result}")
                    except Exception as e:
                        logger.warning(f"Failed to merge completed work to parent: {e}")

                    # Auto-link commit to ticket if task has ticket_id
                    if task.ticket_id and merge_commit_sha:
                        try:
                            logger.info(f"Auto-linking commit {merge_commit_sha} to ticket {task.ticket_id}")

                            # Link the merge commit to the ticket
                            await TicketService.link_commit(
                                ticket_id=task.ticket_id,
                                agent_id=agent_id,
                                commit_sha=merge_commit_sha,
                                commit_message=f"Task {request.task_id} completed and merged",
                                link_method="auto_task_completion"
                            )

                            logger.info(f"Commit {merge_commit_sha} linked to ticket {task.ticket_id}")

                            # Broadcast commit linked to ticket
                            await server_state.broadcast_update({
                                "type": "ticket_commit_linked",
                                "ticket_id": task.ticket_id,
                                "task_id": request.task_id,
                                "agent_id": agent_id,
                                "commit_sha": merge_commit_sha
                            })

                        except Exception as e:
                            logger.error(f"Failed to auto-link commit to ticket: {e}")
                            # Don't fail the task if ticket operations fail

                # 4. Schedule agent termination and queue processing (only if no validation)
                async def terminate_and_process_queue():
                    await server_state.agent_manager.terminate_agent(agent_id)
                    await process_queue()

                asyncio.create_task(terminate_and_process_queue())

            # 5. Broadcast update
            await server_state.broadcast_update({
                "type": "task_completed",
                "task_id": request.task_id,
                "agent_id": agent_id,
                "status": request.status,
                "summary": request.summary[:200],
            })

            session.close()

            # Return appropriate response based on whether validation was spawned
            if validation_spawned:
                return UpdateTaskStatusResponse(
                    success=True,
                    message="Task submitted for validation. A validation agent has been spawned - please wait for validation results.",
                    termination_scheduled=False,  # Agent kept alive for validation feedback
                )
            else:
                return UpdateTaskStatusResponse(
                    success=True,
                    message=f"Task {request.status} successfully",
                    termination_scheduled=True,
                )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to update task status: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @router.post("/api/bump_task_priority")
    async def bump_task_priority_endpoint(
        task_id: str = Body(..., embed=True),
    ):
        """Bump a queued task and start it immediately, bypassing the agent limit.

        This allows urgent tasks to start even when at max capacity (e.g., 2/2 → 3/2).
        When agents complete, the system returns to the configured limit.
        """
        logger.info(f"Priority bump & start request for task {task_id}")

        try:
            session = server_state.db_manager.get_session()
            try:
                # Verify task exists and is queued
                task = session.query(Task).filter_by(id=task_id).first()
                if not task:
                    raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

                if task.status != "queued":
                    raise HTTPException(
                        status_code=400,
                        detail=f"Task {task_id} is not queued (status: {task.status})"
                    )

            finally:
                session.close()

            # Boost the task priority first
            success = server_state.queue_service.boost_task_priority(task_id)
            if not success:
                raise HTTPException(status_code=500, detail="Failed to boost task priority")

            # Dequeue and start immediately (bypassing limit)
            session = server_state.db_manager.get_session()
            try:
                task = session.query(Task).filter_by(id=task_id).first()

                # Dequeue the task
                server_state.queue_service.dequeue_task(task_id)

                # Get project context
                project_context = await server_state.agent_manager.get_project_context()

                # Get phase context if applicable
                if task.phase_id and server_state.phase_manager:
                    phase_context = server_state.phase_manager.get_phase_context(task.phase_id)
                    if phase_context:
                        project_context = f"{project_context}\n\n{phase_context.to_prompt_context()}"

                # Retrieve relevant memories
                context_memories = await server_state.rag_system.retrieve_for_task(
                    task_description=task.enriched_description or task.raw_description,
                    requesting_agent_id="system",
                )

                # Determine working directory
                working_directory = None
                if task.phase_id:
                    phase = session.query(Phase).filter_by(id=task.phase_id).first()
                    if phase and phase.working_directory:
                        working_directory = phase.working_directory
                if not working_directory:
                    working_directory = os.getcwd()

            finally:
                session.close()

            # Create agent immediately (bypassing agent limit)
            agent = await server_state.agent_manager.create_agent_for_task(
                task=task,
                enriched_data={"enriched_description": task.enriched_description},
                memories=context_memories,
                project_context=project_context,
                working_directory=working_directory,
            )

            # Update task status
            session = server_state.db_manager.get_session()
            try:
                task = session.query(Task).filter_by(id=task_id).first()
                if task:
                    task.assigned_agent_id = agent.id
                    task.status = "assigned"
                    task.started_at = datetime.utcnow()
                    session.commit()
            finally:
                session.close()

            # Broadcast update
            await server_state.broadcast_update({
                "type": "task_priority_bumped",
                "task_id": task_id,
                "agent_id": agent.id,
            })

            logger.info(f"Task {task_id} bumped and agent {agent.id} created (bypassing limit)")

            return {
                "success": True,
                "message": f"Task {task_id[:8]} started immediately (bypassing agent limit)",
                "agent_id": agent.id,
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to bump and start task: {e}")
            import traceback
            logger.error(traceback.format_exc())
            raise HTTPException(status_code=500, detail=str(e))

    @router.post("/api/cancel_queued_task")
    async def cancel_queued_task_endpoint(
        task_id: str = Body(..., embed=True),
    ):
        """Cancel a queued task and remove it from the queue.

        The task will be marked as failed and removed from the queue.
        """
        logger.info(f"Cancel request for queued task {task_id}")

        try:
            session = server_state.db_manager.get_session()
            try:
                # Verify task exists and is queued
                task = session.query(Task).filter_by(id=task_id).first()
                if not task:
                    raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

                if task.status != "queued":
                    raise HTTPException(
                        status_code=400,
                        detail=f"Task {task_id} is not queued (status: {task.status})"
                    )

                # Mark task as failed
                task.status = "failed"
                task.failure_reason = "Cancelled by user from queue"
                task.completed_at = datetime.utcnow()
                session.commit()

            finally:
                session.close()

            # Remove from queue
            server_state.queue_service.dequeue_task(task_id)

            # Broadcast update
            await server_state.broadcast_update({
                "type": "task_cancelled",
                "task_id": task_id,
            })

            logger.info(f"Task {task_id} cancelled and removed from queue")

            return {
                "success": True,
                "message": f"Task {task_id[:8]} cancelled and removed from queue",
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to cancel queued task: {e}")
            import traceback
            logger.error(traceback.format_exc())
            raise HTTPException(status_code=500, detail=str(e))

    @router.post("/api/restart_task")
    async def restart_task_endpoint(
        task_id: str = Body(..., embed=True),
    ):
        """Restart a completed or failed task.

        This will:
        - Clear completion data (failure_reason, completion_notes, completed_at)
        - Clear trajectory data (guardian analyses, steering interventions)
        - Reset task to pending/queued status
        - Create new agent or queue based on capacity
        """
        logger.info(f"Restart request for task {task_id}")

        try:
            session = server_state.db_manager.get_session()
            try:
                # Verify task exists and is done/failed
                task = session.query(Task).filter_by(id=task_id).first()
                if not task:
                    raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

                if task.status not in ["done", "failed"]:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Can only restart completed or failed tasks (current status: {task.status})"
                    )

                # Get agent ID before clearing (to delete trajectory data)
                old_agent_id = task.assigned_agent_id

                # Clear completion data
                task.status = "pending"
                task.assigned_agent_id = None
                task.started_at = None
                task.completed_at = None
                task.completion_notes = None
                task.failure_reason = None
                session.commit()

            finally:
                session.close()

            # Clear trajectory data for old agent
            if old_agent_id:
                session = server_state.db_manager.get_session()
                try:
                    from src.core.database import GuardianAnalysis, SteeringIntervention

                    # Delete guardian analyses
                    session.query(GuardianAnalysis).filter_by(agent_id=old_agent_id).delete()

                    # Delete steering interventions
                    session.query(SteeringIntervention).filter_by(agent_id=old_agent_id).delete()

                    session.commit()
                    logger.info(f"Cleared trajectory data for agent {old_agent_id}")

                finally:
                    session.close()

            # Check if we should queue or create agent immediately
            should_queue = server_state.queue_service.should_queue_task()

            if should_queue:
                # Queue the task
                server_state.queue_service.enqueue_task(task_id)
                logger.info(f"Task {task_id} restarted and queued")

                # Broadcast update
                await server_state.broadcast_update({
                    "type": "task_restarted",
                    "task_id": task_id,
                    "status": "queued",
                })

                return {
                    "success": True,
                    "message": f"Task {task_id[:8]} restarted and added to queue",
                    "status": "queued",
                }
            else:
                # Create agent immediately
                session = server_state.db_manager.get_session()
                try:
                    task = session.query(Task).filter_by(id=task_id).first()

                    # Get project context
                    project_context = await server_state.agent_manager.get_project_context()

                    # Get phase context if applicable
                    if task.phase_id and server_state.phase_manager:
                        phase_context = server_state.phase_manager.get_phase_context(task.phase_id)
                        if phase_context:
                            project_context = f"{project_context}\n\n{phase_context.to_prompt_context()}"

                    # Retrieve relevant memories
                    context_memories = await server_state.rag_system.retrieve_for_task(
                        task_description=task.enriched_description or task.raw_description,
                        requesting_agent_id="system",
                    )

                    # Determine working directory
                    working_directory = None
                    if task.phase_id:
                        phase = session.query(Phase).filter_by(id=task.phase_id).first()
                        if phase and phase.working_directory:
                            working_directory = phase.working_directory
                    if not working_directory:
                        working_directory = os.getcwd()

                finally:
                    session.close()

                # Create agent for the task
                agent = await server_state.agent_manager.create_agent_for_task(
                    task=task,
                    enriched_data={"enriched_description": task.enriched_description},
                    memories=context_memories,
                    project_context=project_context,
                    working_directory=working_directory,
                )

                # Update task status
                session = server_state.db_manager.get_session()
                try:
                    task = session.query(Task).filter_by(id=task_id).first()
                    if task:
                        task.assigned_agent_id = agent.id
                        task.status = "assigned"
                        task.started_at = datetime.utcnow()
                        session.commit()
                finally:
                    session.close()

                logger.info(f"Task {task_id} restarted with new agent {agent.id}")

                # Broadcast update
                await server_state.broadcast_update({
                    "type": "task_restarted",
                    "task_id": task_id,
                    "agent_id": agent.id,
                    "status": "assigned",
                })

                return {
                    "success": True,
                    "message": f"Task {task_id[:8]} restarted with new agent",
                    "agent_id": agent.id,
                    "status": "assigned",
                }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to restart task: {e}")
            import traceback
            logger.error(traceback.format_exc())
            raise HTTPException(status_code=500, detail=str(e))

    return router
