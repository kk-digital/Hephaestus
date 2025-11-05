"""MCP Server implementation for Hephaestus."""

from typing import Dict, Any, Optional, List
import json
import uuid
import logging
import os
import time
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, Header, WebSocket, WebSocketDisconnect, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel, Field
import asyncio

from src.core.simple_config import get_config
from src.core.database import DatabaseManager, Task, Agent, Memory, Phase, ValidationReview, AgentResult, WorkflowResult, Workflow, get_db
from src.core.worktree_manager import WorktreeManager
from src.interfaces import get_cli_agent
from src.memory.vector_store import VectorStoreManager
from src.agents.manager import AgentManager
from src.memory.rag import RAGSystem
from src.mcp.api import create_frontend_routes
from src.phases import PhaseManager
from src.auth.auth_api import router as auth_router
from src.services.workflow_result_service import WorkflowResultService
from src.services.result_validator_service import ResultValidatorService
from src.services.embedding_service import EmbeddingService
from src.services.task_similarity_service import TaskSimilarityService
from src.services.queue_service import QueueService
from src.services.ticket_service import TicketService
from src.services.ticket_history_service import TicketHistoryService
from src.services.ticket_search_service import TicketSearchService

# C3 Routes (Application Layer)
from src.c3_health_routes import router as health_router
from src.c3_queue_routes import create_queue_router
from src.c3_workflow_routes import create_workflow_router
from src.c3_websocket_routes import create_websocket_router
from src.c3_messaging_routes import create_messaging_router
from src.c3_task_routes import create_task_router
from src.c3_memory_routes import create_memory_router
from src.c3_agent_routes import create_agent_router
from src.c3_ticket_routes import create_ticket_router
from src.c3_mcp_routes import create_mcp_router
from src.c3_oauth_routes import create_oauth_router

logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Hephaestus MCP Server",
    description="Model Context Protocol server for AI agent orchestration",
    version="1.0.0",
)

# Add CORS middleware
config = get_config()
if config.enable_cors:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


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


class BroadcastMessageRequest(BaseModel):
    """Request model for broadcasting a message to all agents."""

    message: str = Field(..., description="Message content to broadcast")


    clarification: str  # Markdown-formatted detailed response
    comment_id: str  # ID of the comment where clarification was stored
    message: str


class FileDiff(BaseModel):
    """File diff information for commit."""

    path: str
    status: str  # modified, added, deleted, renamed
    insertions: int
    deletions: int
    diff: str  # Unified diff content
    language: str  # For syntax highlighting
    old_path: Optional[str] = None  # For renamed files


class CommitDiffResponse(BaseModel):
    """Response model for commit diff."""

    success: bool
    commit_sha: str
    commit_message: str
    author: str
    commit_timestamp: str
    files_changed: int
    total_insertions: int
    total_deletions: int
    total_files: int
    files: List[FileDiff]


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


# Server state
class ServerState:
    """Global server state."""

    def __init__(self):
        self.db_manager: Optional[DatabaseManager] = None
        self.vector_store: Optional[VectorStoreManager] = None
        self.llm_provider = None
        self.agent_manager: Optional[AgentManager] = None
        self.rag_system: Optional[RAGSystem] = None
        self.phase_manager: Optional[PhaseManager] = None
        self.worktree_manager: Optional[WorktreeManager] = None
        self.result_validator_service: Optional[ResultValidatorService] = None
        self.embedding_service: Optional[EmbeddingService] = None
        self.task_similarity_service: Optional[TaskSimilarityService] = None
        self.queue_service: Optional[QueueService] = None
        self.active_websockets: List[WebSocket] = []
        self.sse_queues: List[asyncio.Queue] = []
        self.background_queue_processor_task: Optional[asyncio.Task] = None
        self.shutdown_event: asyncio.Event = asyncio.Event()

    async def initialize(self):
        """Initialize server components."""
        config = get_config()

        # Initialize database
        self.db_manager = DatabaseManager(str(config.database_path))
        self.db_manager.create_tables()

        # Initialize vector store
        self.vector_store = VectorStoreManager(
            qdrant_url=config.qdrant_url,
            collection_prefix=config.qdrant_collection_prefix,
        )

        # Initialize LLM provider using get_llm_provider()
        # This automatically handles multi-provider config or falls back to legacy single-provider
        from src.interfaces.llm_interface import get_llm_provider
        self.llm_provider = get_llm_provider()

        # Initialize phase manager first (needed by agent manager)
        self.phase_manager = PhaseManager(
            db_manager=self.db_manager
        )

        # Initialize worktree manager
        self.worktree_manager = WorktreeManager(
            db_manager=self.db_manager
        )

        # Initialize agent manager with phase manager
        self.agent_manager = AgentManager(
            db_manager=self.db_manager,
            llm_provider=self.llm_provider,
            phase_manager=self.phase_manager,
        )

        # Initialize RAG system
        self.rag_system = RAGSystem(
            vector_store=self.vector_store,
            llm_provider=self.llm_provider,
        )

        # Initialize result validator service
        self.result_validator_service = ResultValidatorService(
            db_manager=self.db_manager,
            phase_manager=self.phase_manager,
        )

        # Initialize embedding and similarity services (only if OpenAI is configured and dedup enabled)
        if config.openai_api_key and config.task_dedup_enabled:
            self.embedding_service = EmbeddingService(config.openai_api_key)
            self.task_similarity_service = TaskSimilarityService(
                self.db_manager,
                self.embedding_service
            )
            logger.info("Task deduplication service initialized")
        else:
            if not config.openai_api_key:
                logger.warning("OpenAI API key not configured - task deduplication disabled")
            if not config.task_dedup_enabled:
                logger.info("Task deduplication disabled by configuration")

        # Initialize queue service
        self.queue_service = QueueService(
            db_manager=self.db_manager,
            max_concurrent_agents=config.max_concurrent_agents
        )
        logger.info(f"Queue service initialized with max_concurrent_agents={config.max_concurrent_agents}")

        logger.info("Server state initialized successfully")

    async def broadcast_update(self, message: Dict[str, Any]):
        """Broadcast update to all connected WebSocket and SSE clients."""
        disconnected = []
        for websocket in self.active_websockets:
            try:
                await websocket.send_json(message)
            except:
                disconnected.append(websocket)

        # Remove disconnected clients
        for ws in disconnected:
            self.active_websockets.remove(ws)

        # Send to SSE clients
        for queue in self.sse_queues:
            try:
                queue.put_nowait(message)
            except asyncio.QueueFull:
                logger.warning("SSE queue full, skipping event")


# Initialize server state
server_state = ServerState()


def get_single_active_workflow() -> Optional[str]:
    """
    Get the ID of the single active workflow in the system.

    Returns:
        workflow_id if exactly one workflow exists, None otherwise
    """
    try:
        with get_db() as session:
            workflows = session.query(Workflow).filter(
                Workflow.status.in_(["active", "paused"])
            ).all()

            if len(workflows) == 1:
                return workflows[0].id
            elif len(workflows) == 0:
                logger.warning("No active workflows found in the system")
                return None
            else:
                logger.warning(f"Multiple workflows found ({len(workflows)}), cannot auto-select")
                return None
    except Exception as e:
        logger.error(f"Error getting single active workflow: {e}")
        return None


@app.on_event("startup")
async def startup_event():
    """Initialize server on startup."""
    logger.info("Starting Hephaestus MCP Server...")
    await server_state.initialize()

    # Add frontend API routes
    api_router = create_frontend_routes(server_state.db_manager, server_state.agent_manager, server_state.phase_manager)
    app.include_router(api_router)

    # Add authentication routes
    app.include_router(auth_router)

    # Add c3 layer routes (extracted application layer)
    app.include_router(health_router)
    app.include_router(create_queue_router(server_state))
    app.include_router(create_workflow_router(server_state))
    app.include_router(create_websocket_router(server_state))
    app.include_router(create_messaging_router(server_state))
    app.include_router(create_task_router(server_state, process_queue))
    app.include_router(create_memory_router(server_state))
    app.include_router(create_agent_router(server_state, process_queue))
    app.include_router(create_ticket_router(server_state))
    app.include_router(create_mcp_router(server_state))
    app.include_router(create_oauth_router())

    # Load phases if folder is specified
    import os
    from pathlib import Path

    logger.info("=== PHASE LOADING DEBUG ===")
    logger.info(f"Current working directory: {os.getcwd()}")
    logger.info(f"Environment variables starting with HEPHAESTUS: {[k for k in os.environ.keys() if 'HEPHAESTUS' in k]}")

    phases_folder = os.environ.get("HEPHAESTUS_PHASES_FOLDER")
    logger.info(f"HEPHAESTUS_PHASES_FOLDER value: '{phases_folder}'")

    if phases_folder:
        logger.info(f"Attempting to load workflow phases from: {phases_folder}")

        # Check if folder exists
        full_path = Path(phases_folder)
        if not full_path.is_absolute():
            full_path = Path(os.getcwd()) / phases_folder

        logger.info(f"Full path to phases folder: {full_path}")
        logger.info(f"Folder exists: {full_path.exists()}")
        logger.info(f"Is directory: {full_path.is_dir() if full_path.exists() else 'N/A'}")

        if full_path.exists() and full_path.is_dir():
            # List files in directory
            files = list(full_path.glob("*.yaml"))
            logger.info(f"YAML files found: {len(files)}")
            for f in files:
                logger.info(f"  - {f.name}")

        try:
            from src.phases import PhaseLoader
            logger.info("PhaseLoader imported successfully")

            # Load phases from folder
            logger.info(f"Calling PhaseLoader.load_phases_from_folder('{phases_folder}')")
            workflow_def = PhaseLoader.load_phases_from_folder(phases_folder)
            logger.info(f"Loaded workflow '{workflow_def.name}' with {len(workflow_def.phases)} phases")

            # Load phases configuration (for ticket tracking, result handling, etc.)
            logger.info(f"Loading phases_config.yaml from '{phases_folder}'")
            phases_config = PhaseLoader.load_phases_config(phases_folder)
            logger.info(f"Loaded phases config: enable_tickets={phases_config.enable_tickets}, has_result={phases_config.has_result}")

            # Initialize workflow in database
            logger.info("Initializing workflow in database...")
            workflow_id = server_state.phase_manager.initialize_workflow(workflow_def, phases_config)
            logger.info(f"Initialized workflow with ID: {workflow_id}")

            # Log phase names
            logger.info("Loaded phases:")
            for phase in workflow_def.phases:
                logger.info(f"  Phase {phase.order}: {phase.name}")
                logger.info(f"    - Description: {phase.description[:100]}...")
                logger.info(f"    - Done definitions: {len(phase.done_definitions)} items")

        except ImportError as e:
            logger.error(f"Failed to import PhaseLoader: {e}")
            import traceback
            logger.error(traceback.format_exc())
        except Exception as e:
            logger.error(f"Failed to load phases: {e}")
            import traceback
            logger.error(f"Full traceback:\n{traceback.format_exc()}")
            # Don't fail server startup, just run without phases
    else:
        logger.info("No phases folder specified - running in standard mode")
        logger.info("To load phases, set HEPHAESTUS_PHASES_FOLDER environment variable")

    logger.info("=== END PHASE LOADING DEBUG ===")

    # Start background queue processor
    logger.info("Starting background queue processor...")
    server_state.background_queue_processor_task = asyncio.create_task(background_queue_processor())
    logger.info("Background queue processor task created")

    logger.info("Server started successfully")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("Shutting down Hephaestus MCP Server...")

    # Stop background queue processor
    logger.info("Stopping background queue processor...")
    server_state.shutdown_event.set()
    if server_state.background_queue_processor_task:
        try:
            await asyncio.wait_for(server_state.background_queue_processor_task, timeout=5.0)
            logger.info("Background queue processor stopped")
        except asyncio.TimeoutError:
            logger.warning("Background queue processor did not stop gracefully, cancelling...")
            server_state.background_queue_processor_task.cancel()

    # Close all WebSocket connections
    for ws in server_state.active_websockets:
        await ws.close()


def verify_agent_id(agent_id: str = Header(None, alias="X-Agent-ID")) -> str:
    """Verify agent ID from header."""
    if not agent_id:
        raise HTTPException(status_code=401, detail="Agent ID required in X-Agent-ID header")
    return agent_id


async def process_queue():
    """Process the next queued task by creating an agent for it.

    Only creates an agent if we're under the max concurrent agent limit.
    """
    try:
        # Check if we should queue (i.e., at capacity)
        if server_state.queue_service.should_queue_task():
            logger.debug("At capacity - not processing queue")
            return

        # Get next task from queue
        next_task = server_state.queue_service.get_next_queued_task()

        if not next_task:
            logger.debug("No queued tasks to process")
            return

        logger.info(f"Processing queued task {next_task.id} (priority={next_task.priority}, boosted={next_task.priority_boosted})")

        # Dequeue the task
        server_state.queue_service.dequeue_task(next_task.id)

        # BUG FIX: Check if task needs enrichment (was blocked on creation and skipped enrichment)
        # Tasks created with placeholder "[Processing] ..." need real LLM enrichment
        needs_enrichment = not next_task.enriched_description or next_task.enriched_description.startswith("[Processing]")
        logger.info(f"[QUEUE_ENRICHMENT] Task {next_task.id} enrichment check:")
        logger.info(f"[QUEUE_ENRICHMENT]   - enriched_description exists: {bool(next_task.enriched_description)}")
        logger.info(f"[QUEUE_ENRICHMENT]   - enriched_description value: {next_task.enriched_description[:100] if next_task.enriched_description else 'NULL'}")
        logger.info(f"[QUEUE_ENRICHMENT]   - starts with [Processing]: {next_task.enriched_description.startswith('[Processing]') if next_task.enriched_description else False}")
        logger.info(f"[QUEUE_ENRICHMENT]   - NEEDS ENRICHMENT: {needs_enrichment}")

        if needs_enrichment:
            logger.info(f"[QUEUE_ENRICHMENT] ========== STARTING ENRICHMENT PIPELINE FOR TASK {next_task.id} ==========")
            logger.info(f"[QUEUE_ENRICHMENT] Task phase_id (from DB): {next_task.phase_id} (type: {type(next_task.phase_id).__name__})")
            logger.info(f"[QUEUE_ENRICHMENT] Task raw_description: {next_task.raw_description[:200]}")

            # Get phase context for enrichment
            # CRITICAL: phase_id might be an integer (phase order) or UUID string
            phase_context_str = ""
            workflow_id = None
            phase_id_uuid = None

            if next_task.phase_id and server_state.phase_manager:
                # BUG FIX: Convert phase order number to UUID (same logic as process_task_async)
                logger.info(f"[QUEUE_ENRICHMENT] Converting phase_id to UUID if needed")
                logger.info(f"[QUEUE_ENRICHMENT]   - Original phase_id: {next_task.phase_id}")
                logger.info(f"[QUEUE_ENRICHMENT]   - Is digit check: {str(next_task.phase_id).isdigit()}")

                if str(next_task.phase_id).isdigit():
                    # phase_id is a phase order number - convert to UUID
                    logger.info(f"[QUEUE_ENRICHMENT] phase_id={next_task.phase_id} is an ORDER number - converting to UUID")
                    phase_id_uuid = server_state.phase_manager.get_phase_for_task(
                        phase_id=None,
                        order=int(next_task.phase_id),
                        requesting_agent_id="system"
                    )
                    logger.info(f"[QUEUE_ENRICHMENT] ✓ Converted phase order {next_task.phase_id} → UUID: {phase_id_uuid}")
                else:
                    # phase_id is already a UUID
                    logger.info(f"[QUEUE_ENRICHMENT] phase_id={next_task.phase_id} is a UUID - using directly")
                    phase_id_uuid = next_task.phase_id

                logger.info(f"[QUEUE_ENRICHMENT] Fetching phase context for UUID: {phase_id_uuid}")
                phase_context = server_state.phase_manager.get_phase_context(phase_id_uuid)
                if phase_context:
                    phase_context_str = phase_context.to_prompt_context()
                    workflow_id = phase_context.workflow_id
                    logger.info(f"[QUEUE_ENRICHMENT] ✓ Got phase context (length={len(phase_context_str)}, workflow_id={workflow_id})")
                    logger.info(f"[QUEUE_ENRICHMENT] Phase context preview: {phase_context_str[:300]}")
                else:
                    logger.warning(f"[QUEUE_ENRICHMENT] ✗ No phase context returned for phase UUID={phase_id_uuid}")
            else:
                logger.warning(f"[QUEUE_ENRICHMENT] ✗ Skipping phase context (phase_id={next_task.phase_id}, phase_manager={bool(server_state.phase_manager)})")

            # BUG FIX: If we don't have workflow_id from phase, try to get it from single active workflow
            if not workflow_id:
                logger.info(f"[QUEUE_ENRICHMENT] No workflow_id from phase context - trying get_single_active_workflow()")
                workflow_id = get_single_active_workflow()
                if workflow_id:
                    logger.info(f"[QUEUE_ENRICHMENT] ✓ Got workflow_id from single active workflow: {workflow_id}")
                else:
                    logger.warning(f"[QUEUE_ENRICHMENT] ✗ Could not get workflow_id from single active workflow")

            # Retrieve RAG memories for enrichment
            logger.info(f"[QUEUE_ENRICHMENT] Retrieving RAG memories for enrichment")
            context_memories_for_enrichment = await server_state.rag_system.retrieve_for_task(
                task_description=next_task.raw_description,
                requesting_agent_id="system",
            )
            logger.info(f"[QUEUE_ENRICHMENT] ✓ Retrieved {len(context_memories_for_enrichment)} memories from RAG")

            # Get project context for enrichment
            logger.info(f"[QUEUE_ENRICHMENT] Getting project context")
            project_context_for_enrichment = await server_state.agent_manager.get_project_context()
            logger.info(f"[QUEUE_ENRICHMENT] ✓ Got project context (length={len(project_context_for_enrichment)})")

            if phase_context_str:
                project_context_for_enrichment = f"{project_context_for_enrichment}\n\n{phase_context_str}"
                logger.info(f"[QUEUE_ENRICHMENT] ✓ Added phase context to project context (total length={len(project_context_for_enrichment)})")

            # Enrich task using LLM
            logger.info(f"[QUEUE_ENRICHMENT] Calling LLM for task enrichment")
            logger.info(f"[QUEUE_ENRICHMENT]   - task_description: {next_task.raw_description[:100]}")
            logger.info(f"[QUEUE_ENRICHMENT]   - done_definition: {next_task.done_definition}")
            logger.info(f"[QUEUE_ENRICHMENT]   - context memories: {len(context_memories_for_enrichment)} items")
            logger.info(f"[QUEUE_ENRICHMENT]   - phase_context provided: {bool(phase_context_str)}")

            context_strings = [mem.get("content", "") for mem in context_memories_for_enrichment]
            enriched_task = await server_state.llm_provider.enrich_task(
                task_description=next_task.raw_description,
                done_definition=next_task.done_definition or "Task completed successfully",
                context=context_strings,
                phase_context=phase_context_str if phase_context_str else None,
            )
            logger.info(f"[QUEUE_ENRICHMENT] ✓ LLM enrichment complete!")
            logger.info(f"[QUEUE_ENRICHMENT] Enriched description: {enriched_task['enriched_description'][:200]}")
            logger.info(f"[QUEUE_ENRICHMENT] Estimated complexity: {enriched_task.get('estimated_complexity', 'N/A')}")

            # Update task with enriched data
            logger.info(f"[QUEUE_ENRICHMENT] Updating task in database")
            session = server_state.db_manager.get_session()
            try:
                task = session.query(Task).filter_by(id=next_task.id).first()
                if task:
                    task.enriched_description = enriched_task["enriched_description"]
                    task.estimated_complexity = enriched_task.get("estimated_complexity", 5)
                    logger.info(f"[QUEUE_ENRICHMENT] ✓ Set enriched_description and estimated_complexity")

                    # BUG FIX: Update phase_id to UUID if we converted it from order
                    if phase_id_uuid and phase_id_uuid != next_task.phase_id:
                        logger.info(f"[QUEUE_ENRICHMENT] Updating phase_id from order {next_task.phase_id} to UUID {phase_id_uuid}")
                        task.phase_id = phase_id_uuid
                        next_task.phase_id = phase_id_uuid  # Update in-memory object too
                        logger.info(f"[QUEUE_ENRICHMENT] ✓ Updated phase_id to UUID in database")

                    # BUG FIX: Always set workflow_id (to match process_task_async behavior)
                    if workflow_id:
                        task.workflow_id = workflow_id
                        logger.info(f"[QUEUE_ENRICHMENT] ✓ Set workflow_id: {workflow_id}")
                    else:
                        logger.warning(f"[QUEUE_ENRICHMENT] ✗ No workflow_id to set")

                    # Check if phase has validation enabled
                    if phase_id_uuid:
                        from src.core.database import Phase
                        phase = session.query(Phase).filter_by(id=phase_id_uuid).first()
                        if phase and phase.validation:
                            if phase.validation.get("enabled", True):
                                task.validation_enabled = True
                                logger.info(f"[QUEUE_ENRICHMENT] ✓ Inherited validation from phase (enabled=True)")
                            else:
                                logger.info(f"[QUEUE_ENRICHMENT] Phase validation explicitly disabled")
                        else:
                            logger.info(f"[QUEUE_ENRICHMENT] No validation config in phase")

                    session.commit()
                    logger.info(f"[QUEUE_ENRICHMENT] ✓ Database commit successful")

                    # Store enriched_task dict for passing to create_agent_for_task
                    next_task.enriched_description = enriched_task["enriched_description"]
                    next_task._enriched_task_dict = enriched_task  # Store full dict
                    logger.info(f"[QUEUE_ENRICHMENT] ✓ Stored full enriched_task dict for agent creation")
                    logger.info(f"[QUEUE_ENRICHMENT] ========== ENRICHMENT PIPELINE COMPLETE FOR TASK {next_task.id} ==========")
                else:
                    logger.error(f"[QUEUE_ENRICHMENT] ✗ Task {next_task.id} not found in database!")
            finally:
                session.close()
        else:
            logger.info(f"[QUEUE_ENRICHMENT] Task {next_task.id} already enriched - skipping enrichment pipeline")

        # BUG FIX: Refresh task from database first to get enriched_description for RAG retrieval
        session_pre = server_state.db_manager.get_session()
        try:
            refreshed_task_pre = session_pre.query(Task).filter_by(id=next_task.id).first()
            task_description_for_rag = refreshed_task_pre.enriched_description or refreshed_task_pre.raw_description
        finally:
            session_pre.close()

        # Get project context
        logger.info(f"[QUEUE_AGENT_CREATE] Getting project context for task {next_task.id}")
        project_context = await server_state.agent_manager.get_project_context()
        logger.info(f"[QUEUE_AGENT_CREATE] ✓ Got project context (length={len(project_context)})")

        # Get phase context if applicable
        # BUG FIX: Convert phase order to UUID (same as enrichment above)
        phase_id_for_agent = None
        if next_task.phase_id and server_state.phase_manager:
            logger.info(f"[QUEUE_AGENT_CREATE] Converting phase_id for agent creation")
            logger.info(f"[QUEUE_AGENT_CREATE]   - phase_id from task: {next_task.phase_id}")

            if str(next_task.phase_id).isdigit():
                logger.info(f"[QUEUE_AGENT_CREATE] phase_id={next_task.phase_id} is ORDER - converting to UUID")
                phase_id_for_agent = server_state.phase_manager.get_phase_for_task(
                    phase_id=None,
                    order=int(next_task.phase_id),
                    requesting_agent_id="system"
                )
                logger.info(f"[QUEUE_AGENT_CREATE] ✓ Converted order {next_task.phase_id} → UUID: {phase_id_for_agent}")
            else:
                logger.info(f"[QUEUE_AGENT_CREATE] phase_id={next_task.phase_id} is UUID - using directly")
                phase_id_for_agent = next_task.phase_id

            logger.info(f"[QUEUE_AGENT_CREATE] Fetching phase context for agent with UUID: {phase_id_for_agent}")
            phase_context = server_state.phase_manager.get_phase_context(phase_id_for_agent)
            if phase_context:
                project_context = f"{project_context}\n\n{phase_context.to_prompt_context()}"
                logger.info(f"[QUEUE_AGENT_CREATE] ✓ Added phase context to project context (total={len(project_context)})")
            else:
                logger.warning(f"[QUEUE_AGENT_CREATE] ✗ No phase context for UUID: {phase_id_for_agent}")

        # Retrieve relevant memories (using enriched description if available)
        logger.info(f"[QUEUE_AGENT_CREATE] Retrieving RAG memories")
        context_memories = await server_state.rag_system.retrieve_for_task(
            task_description=task_description_for_rag,
            requesting_agent_id="system",
        )
        logger.info(f"[QUEUE_AGENT_CREATE] ✓ Retrieved {len(context_memories)} memories")

        # Determine working directory
        working_directory = None
        if phase_id_for_agent:
            logger.info(f"[QUEUE_AGENT_CREATE] Querying database for phase working directory")
            session = server_state.db_manager.get_session()
            try:
                from src.core.database import Phase

                # DEBUG: Show what's in the Phase table
                logger.info(f"[QUEUE_AGENT_CREATE] DEBUG: Querying Phase table with UUID: {phase_id_for_agent}")
                all_phases = session.query(Phase.id, Phase.name, Phase.order).all()
                logger.info(f"[QUEUE_AGENT_CREATE] DEBUG: All phases in DB: {all_phases}")

                phase = session.query(Phase).filter_by(id=phase_id_for_agent).first()
                if phase:
                    logger.info(f"[QUEUE_AGENT_CREATE] ✓ Found phase: {phase.name}, working_dir: {phase.working_directory}")
                    if phase.working_directory:
                        working_directory = phase.working_directory
                else:
                    logger.warning(f"[QUEUE_AGENT_CREATE] ✗ No phase found with UUID: {phase_id_for_agent}")
            finally:
                session.close()
        if not working_directory:
            working_directory = os.getcwd()
            logger.info(f"[QUEUE_AGENT_CREATE] Using default working directory: {working_directory}")

        # BUG FIX: Refresh task from database to get updated enriched_description
        # The next_task object is stale if enrichment just ran
        logger.info(f"[QUEUE_AGENT_CREATE] Refreshing task from database")
        session = server_state.db_manager.get_session()
        try:
            refreshed_task = session.query(Task).filter_by(id=next_task.id).first()
            if refreshed_task:
                logger.info(f"[QUEUE_AGENT_CREATE] ✓ Refreshed task from DB")
                logger.info(f"[QUEUE_AGENT_CREATE]   - enriched_description: {refreshed_task.enriched_description[:100] if refreshed_task.enriched_description else 'NULL'}")
                logger.info(f"[QUEUE_AGENT_CREATE]   - phase_id: {refreshed_task.phase_id}")

                # BUG FIX: Use the UUID phase_id for the temp task, not the order number
                # Create temp task object with fresh data (like normal flow does)
                temp_task = Task(
                    id=refreshed_task.id,
                    raw_description=refreshed_task.raw_description,
                    enriched_description=refreshed_task.enriched_description,
                    done_definition=refreshed_task.done_definition,
                    phase_id=phase_id_for_agent or refreshed_task.phase_id,  # Use UUID if converted
                    created_by_agent_id=refreshed_task.created_by_agent_id,
                )
                task_for_agent = temp_task
                logger.info(f"[QUEUE_AGENT_CREATE] ✓ Created temp task object for agent (phase_id={temp_task.phase_id})")
            else:
                # Fallback to next_task if refresh failed
                logger.warning(f"[QUEUE_AGENT_CREATE] ✗ Could not refresh task from DB - using stale task")
                task_for_agent = next_task
        finally:
            session.close()

        # BUG FIX: Prepare enriched_data dict to match process_task_async exactly
        # If we just ran enrichment, use the full dict; otherwise create minimal dict
        logger.info(f"[QUEUE_AGENT_CREATE] Preparing enriched_data for agent")
        if hasattr(next_task, '_enriched_task_dict'):
            # Enrichment just ran - use full dict from LLM
            enriched_data_for_agent = next_task._enriched_task_dict
            logger.info(f"[QUEUE_AGENT_CREATE] ✓ Using full enriched_task dict from LLM")
        else:
            # Task was already enriched - create minimal dict with enriched_description
            enriched_data_for_agent = {
                "enriched_description": task_for_agent.enriched_description,
                "estimated_complexity": task_for_agent.estimated_complexity or 5,
            }
            logger.info(f"[QUEUE_AGENT_CREATE] ✓ Created minimal enriched_data dict")

        logger.info(f"[QUEUE_AGENT_CREATE] Creating agent for task {next_task.id}")
        logger.info(f"[QUEUE_AGENT_CREATE]   - task enriched_description: {task_for_agent.enriched_description[:100] if task_for_agent.enriched_description else 'NULL'}")
        logger.info(f"[QUEUE_AGENT_CREATE]   - task phase_id: {task_for_agent.phase_id}")
        logger.info(f"[QUEUE_AGENT_CREATE]   - project_context length: {len(project_context)}")
        logger.info(f"[QUEUE_AGENT_CREATE]   - memories count: {len(context_memories)}")
        logger.info(f"[QUEUE_AGENT_CREATE]   - working_directory: {working_directory}")

        # Create agent for the task (using refreshed task data and full enriched_data)
        agent = await server_state.agent_manager.create_agent_for_task(
            task=task_for_agent,
            enriched_data=enriched_data_for_agent,
            memories=context_memories,
            project_context=project_context,
            working_directory=working_directory,
        )

        logger.info(f"[QUEUE_AGENT_CREATE] ✓✓✓ AGENT CREATED SUCCESSFULLY: {agent.id} for task {next_task.id} ✓✓✓")

        # Update task status
        session = server_state.db_manager.get_session()
        try:
            task = session.query(Task).filter_by(id=next_task.id).first()
            if task:
                task.assigned_agent_id = agent.id
                task.status = "assigned"
                task.started_at = datetime.utcnow()
                session.commit()
        finally:
            session.close()

        # Broadcast update
        await server_state.broadcast_update({
            "type": "task_dequeued",
            "task_id": next_task.id,
            "agent_id": agent.id,
            "description": (next_task.enriched_description or next_task.raw_description)[:200],
        })

        logger.info(f"Created agent {agent.id} for queued task {next_task.id}")

    except Exception as e:
        logger.error(f"Failed to process queue: {e}")
        import traceback
        logger.error(traceback.format_exc())


async def background_queue_processor():
    """Background task that processes the queue every minute.

    This ensures that queued tasks (especially newly unblocked ones)
    don't get stuck waiting for another event to trigger queue processing.
    """
    logger.info("Background queue processor started")

    while not server_state.shutdown_event.is_set():
        try:
            # Check if there are any queued tasks
            queue_status = server_state.queue_service.get_queue_status()
            queued_count = queue_status.get("queued_tasks_count", 0)

            if queued_count > 0:
                logger.info(f"[BACKGROUND_QUEUE] Found {queued_count} queued task(s), processing queue...")
                await process_queue()
            else:
                logger.debug("[BACKGROUND_QUEUE] No queued tasks, skipping")

        except Exception as e:
            logger.error(f"[BACKGROUND_QUEUE] Error in background queue processor: {e}")
            import traceback
            logger.error(traceback.format_exc())

        # Wait 60 seconds before next check
        try:
            await asyncio.wait_for(server_state.shutdown_event.wait(), timeout=60.0)
            # If we get here, shutdown was signaled
            break
        except asyncio.TimeoutError:
            # Timeout is expected - continue the loop
            pass

    logger.info("Background queue processor stopped")













        # Get file stats from the correct repository





            # Get unified diff for this file from the correct repository

            # Determine file status







# EXTRACTED TO: src/c3_health_routes/health_routes.py
# @app.get("/health")
# async def health_check():
#     """Health check endpoint."""
#     return {
#         "status": "healthy",
#         "timestamp": datetime.utcnow().isoformat(),
#         "version": "1.0.0",
#     }



