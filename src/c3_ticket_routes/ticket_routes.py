"""Ticket management routes for Hephaestus MCP server."""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

from fastapi import APIRouter, HTTPException, Header, Body
from pydantic import BaseModel, Field

from src.c1_agent_models.agent import Agent
from src.c1_task_models.task import Task
from src.c2_ticket_service.ticket_service import TicketService
from src.c1_database_session.database_manager import get_db

logger = logging.getLogger(__name__)


# Request/Response Models
class CreateTicketRequest(BaseModel):
    title: str = Field(..., description="Ticket title")
    description: str = Field("", description="Detailed description")
    ticket_type: str = Field("task", description="Type: task, bug, feature, etc.")
    priority: str = Field("medium", description="Priority: low, medium, high, critical")
    initial_status: Optional[str] = Field(None, description="Initial status column")
    assigned_agent_id: Optional[str] = Field(None, description="Agent to assign")
    parent_ticket_id: Optional[str] = Field(None, description="Parent ticket ID")
    blocked_by_ticket_ids: Optional[List[str]] = Field(None, description="Blocking ticket IDs")
    tags: Optional[List[str]] = Field(None, description="Tags for categorization")
    workflow_id: Optional[str] = Field(None, description="Workflow ID (auto-detected if not provided)")
    related_task_ids: Optional[List[str]] = Field(None, description="Related task IDs")


class CreateTicketResponse(BaseModel):
    ticket_id: str
    workflow_id: str
    status: str
    message: str
    ticket_number: Optional[int] = None  # Optional for backward compatibility


class UpdateTicketRequest(BaseModel):
    ticket_id: str = Field(..., description="Ticket ID to update")
    updates: Dict[str, Any] = Field(..., description="Fields to update")
    update_comment: Optional[str] = Field(None, description="Comment explaining the update")


class UpdateTicketResponse(BaseModel):
    ticket_id: str
    fields_updated: List[str]
    message: str


class ChangeTicketStatusRequest(BaseModel):
    ticket_id: str = Field(..., description="Ticket ID")
    new_status: str = Field(..., description="New status column")
    status_change_comment: Optional[str] = Field(None, description="Comment for status change")
    resolution_notes: Optional[str] = Field(None, description="Resolution notes (for done/closed)")


class ChangeTicketStatusResponse(BaseModel):
    ticket_id: str
    old_status: str
    new_status: str
    message: str


class AddCommentRequest(BaseModel):
    ticket_id: str = Field(..., description="Ticket ID")
    comment_text: str = Field(..., description="Comment text")
    comment_type: str = Field("general", description="Comment type")
    mentions: Optional[List[str]] = Field(None, description="Mentioned agent/ticket IDs")
    attachments: Optional[List[str]] = Field(None, description="File attachments")


class AddCommentResponse(BaseModel):
    success: bool
    comment_id: str
    ticket_id: str
    message: str


class SearchTicketsRequest(BaseModel):
    workflow_id: Optional[str] = Field(None, description="Filter by workflow")
    ticket_type: Optional[str] = Field(None, description="Filter by type")
    priority: Optional[str] = Field(None, description="Filter by priority")
    status: Optional[str] = Field(None, description="Filter by status")
    assigned_agent_id: Optional[str] = Field(None, description="Filter by assigned agent")
    tags: Optional[List[str]] = Field(None, description="Filter by tags (AND logic)")
    search_text: Optional[str] = Field(None, description="Text search in title/description")
    parent_ticket_id: Optional[str] = Field(None, description="Filter by parent ticket")
    created_after: Optional[datetime] = Field(None, description="Filter by creation date")
    created_before: Optional[datetime] = Field(None, description="Filter by creation date")
    updated_after: Optional[datetime] = Field(None, description="Filter by update date")
    updated_before: Optional[datetime] = Field(None, description="Filter by update date")
    blocked_by_ticket_id: Optional[str] = Field(None, description="Filter tickets blocked by this ticket")
    blocking_ticket_id: Optional[str] = Field(None, description="Filter tickets blocking this ticket")
    include_archived: bool = Field(False, description="Include archived tickets")
    sort_by: str = Field("created_at", description="Sort field")
    sort_order: str = Field("desc", description="Sort order (asc/desc)")
    limit: int = Field(50, description="Max results", ge=1, le=1000)
    offset: int = Field(0, description="Pagination offset", ge=0)


class SearchTicketsResponse(BaseModel):
    tickets: List[Dict[str, Any]]
    total_count: int
    limit: int
    offset: int


class GetTicketsResponse(BaseModel):
    tickets: List[Dict[str, Any]]
    workflow_id: str
    total_count: int


class ResolveTicketRequest(BaseModel):
    ticket_id: str = Field(..., description="Ticket ID to resolve")
    resolution_notes: str = Field(..., description="Resolution explanation")
    new_status: str = Field("done", description="Status to set (done/closed)")


class ResolveTicketResponse(BaseModel):
    ticket_id: str
    status: str
    message: str


class LinkCommitRequest(BaseModel):
    ticket_id: str = Field(..., description="Ticket ID")
    commit_hash: str = Field(..., description="Git commit hash")
    commit_message: Optional[str] = Field(None, description="Commit message")
    repository_url: Optional[str] = Field(None, description="Repository URL")


class LinkCommitResponse(BaseModel):
    ticket_id: str
    commit_hash: str
    message: str


class RequestTicketClarificationRequest(BaseModel):
    ticket_id: str = Field(..., description="Ticket ID")
    clarification_request: str = Field(..., description="What needs clarification")
    block_ticket: bool = Field(True, description="Block ticket until clarified")


class RequestTicketClarificationResponse(BaseModel):
    ticket_id: str
    clarification_request_id: str
    message: str


def create_ticket_router(server_state):
    """Create ticket router with server_state dependency.

    Args:
        server_state: ServerState instance with db_manager, agent_manager, etc.

    Returns:
        APIRouter: Configured router with ticket endpoints
    """
    router = APIRouter(tags=["tickets"])

    @router.post("/api/tickets/create", response_model=CreateTicketResponse)
    async def create_ticket_endpoint(
        request: CreateTicketRequest,
        agent_id: str = Header(..., alias="X-Agent-ID"),
    ):
        """Create a new ticket in the workflow tracking system."""
        logger.info(f"[TICKET_CREATE] ========== START ==========")
        logger.info(f"[TICKET_CREATE] Agent: {agent_id}")
        logger.info(f"[TICKET_CREATE] Title: {request.title}")
        logger.info(f"[TICKET_CREATE] Type: {request.ticket_type}, Priority: {request.priority}")
        logger.info(f"[TICKET_CREATE] Workflow_ID provided: {request.workflow_id}")
        logger.info(f"[TICKET_CREATE] Tags: {request.tags}")

        try:
            # Auto-detect workflow_id from agent's current task if not provided
            workflow_id = request.workflow_id
            if not workflow_id:
                logger.info(f"[TICKET_CREATE] No workflow_id provided, attempting auto-detection...")

                # Try to get from agent's current task first
                with get_db() as session:
                    agent = session.query(Agent).filter_by(id=agent_id).first()
                    logger.info(f"[TICKET_CREATE] Agent lookup: found={agent is not None}")
                    if agent:
                        logger.info(f"[TICKET_CREATE] Agent.current_task_id: {agent.current_task_id}")

                    if agent and agent.current_task_id:
                        task = session.query(Task).filter_by(id=agent.current_task_id).first()
                        logger.info(f"[TICKET_CREATE] Task lookup: found={task is not None}")
                        if task:
                            logger.info(f"[TICKET_CREATE] Task.workflow_id: {task.workflow_id}")

                        if task and task.workflow_id:
                            workflow_id = task.workflow_id
                            logger.info(f"[TICKET_CREATE] ✅ Auto-detected workflow_id from task: {workflow_id}")

                # If still no workflow_id, try to get the single active workflow
                if not workflow_id:
                    from src.mcp.server import get_single_active_workflow
                    logger.info(f"[TICKET_CREATE] Could not detect from task, trying single active workflow...")
                    workflow_id = get_single_active_workflow()
                    if workflow_id:
                        logger.info(f"[TICKET_CREATE] ✅ Using single active workflow: {workflow_id}")
                    else:
                        logger.error(f"[TICKET_CREATE] ❌ No single active workflow found")
                        raise HTTPException(
                            status_code=400,
                            detail="Could not determine workflow_id: no active workflows found or multiple workflows exist. "
                                   "Please ensure you have exactly one active workflow."
                        )
            else:
                logger.info(f"[TICKET_CREATE] Using provided workflow_id: {workflow_id}")

            logger.info(f"[TICKET_CREATE] Calling TicketService.create_ticket with workflow_id={workflow_id}")
            result = await TicketService.create_ticket(
                workflow_id=workflow_id,
                agent_id=agent_id,
                title=request.title,
                description=request.description,
                ticket_type=request.ticket_type,
                priority=request.priority,
                initial_status=request.initial_status,
                assigned_agent_id=request.assigned_agent_id,
                parent_ticket_id=request.parent_ticket_id,
                blocked_by_ticket_ids=request.blocked_by_ticket_ids,
                tags=request.tags,
                related_task_ids=request.related_task_ids,
            )

            logger.info(f"[TICKET_CREATE] ✅ TicketService.create_ticket returned successfully")
            logger.info(f"[TICKET_CREATE] Result: {result}")
            logger.info(f"[TICKET_CREATE] Ticket ID: {result.get('ticket_id')}")

            # Broadcast update
            logger.info(f"[TICKET_CREATE] Broadcasting update...")
            await server_state.broadcast_update({
                "type": "ticket_created",
                "ticket_id": result["ticket_id"],
                "workflow_id": workflow_id,
                "agent_id": agent_id,
                "title": request.title,
            })
            logger.info(f"[TICKET_CREATE] Broadcast complete")

            logger.info(f"[TICKET_CREATE] Creating response object...")
            response = CreateTicketResponse(**result)
            logger.info(f"[TICKET_CREATE] Response created: {response}")
            logger.info(f"[TICKET_CREATE] ========== SUCCESS ==========")
            return response

        except HTTPException:
            # Re-raise HTTPException without modification to preserve status code
            raise
        except ValueError as e:
            logger.error(f"[TICKET_CREATE] ❌ ValueError: {e}")
            logger.error(f"[TICKET_CREATE] ========== FAILED (ValueError) ==========")
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f"[TICKET_CREATE] ❌ Unexpected error: {type(e).__name__}: {e}")
            logger.error(f"[TICKET_CREATE] ========== FAILED (Exception) ==========")
            import traceback
            logger.error(f"[TICKET_CREATE] Traceback: {traceback.format_exc()}")
            raise HTTPException(status_code=500, detail=str(e))

    @router.post("/api/tickets/update", response_model=UpdateTicketResponse)
    async def update_ticket_endpoint(
        request: UpdateTicketRequest,
        agent_id: str = Header(..., alias="X-Agent-ID"),
    ):
        """Update ticket fields (excluding status changes)."""
        logger.info(f"Agent {agent_id} updating ticket {request.ticket_id}")

        try:
            result = await TicketService.update_ticket(
                ticket_id=request.ticket_id,
                agent_id=agent_id,
                updates=request.updates,
                update_comment=request.update_comment,
            )

            # Broadcast update
            await server_state.broadcast_update({
                "type": "ticket_updated",
                "ticket_id": request.ticket_id,
                "agent_id": agent_id,
                "fields_updated": result["fields_updated"],
            })

            return UpdateTicketResponse(**result)

        except ValueError as e:
            logger.error(f"Validation error updating ticket: {e}")
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f"Failed to update ticket: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @router.post("/api/tickets/change-status", response_model=ChangeTicketStatusResponse)
    async def change_ticket_status_endpoint(
        request: ChangeTicketStatusRequest,
        agent_id: str = Header(..., alias="X-Agent-ID"),
    ):
        """Move ticket to a different status column."""
        logger.info(f"Agent {agent_id} changing status of ticket {request.ticket_id} to {request.new_status}")

        try:
            result = await TicketService.change_status(
                ticket_id=request.ticket_id,
                agent_id=agent_id,
                new_status=request.new_status,
                comment=request.status_change_comment or "",
                commit_sha=None,
            )

            # Broadcast update
            await server_state.broadcast_update({
                "type": "ticket_status_changed",
                "ticket_id": request.ticket_id,
                "agent_id": agent_id,
                "old_status": result["old_status"],
                "new_status": request.new_status,
            })

            return ChangeTicketStatusResponse(**result)

        except ValueError as e:
            logger.error(f"Validation error changing ticket status: {e}")
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f"Failed to change ticket status: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @router.post("/api/tickets/comment", response_model=AddCommentResponse)
    async def add_comment_endpoint(
        request: AddCommentRequest,
        agent_id: str = Header(..., alias="X-Agent-ID"),
    ):
        """Add a comment to a ticket."""
        logger.info(f"Agent {agent_id} adding comment to ticket {request.ticket_id}")

        try:
            result = await TicketService.add_comment(
                ticket_id=request.ticket_id,
                agent_id=agent_id,
                comment_text=request.comment_text,
                comment_type=request.comment_type,
                mentions=request.mentions,
                attachments=request.attachments,
            )

            return AddCommentResponse(**result)

        except ValueError as e:
            logger.error(f"Validation error adding comment: {e}")
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f"Failed to add comment: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @router.get("/api/tickets/{ticket_id}")
    async def get_ticket_endpoint(
        ticket_id: str,
        agent_id: str = Header(..., alias="X-Agent-ID"),
    ):
        """Get a single ticket by ID with full details."""
        logger.info(f"Agent {agent_id} requesting ticket {ticket_id}")

        try:
            ticket_data = await TicketService.get_ticket(ticket_id)

            if not ticket_data:
                raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found")

            # Service returns {ticket: {...}, comments: [], history: [], commits: []}
            # For this endpoint, return the full structure including related data
            return ticket_data

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to get ticket: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @router.post("/api/tickets/search", response_model=SearchTicketsResponse)
    async def search_tickets_endpoint(
        request: SearchTicketsRequest,
        agent_id: str = Header(..., alias="X-Agent-ID"),
    ):
        """Search and filter tickets with advanced criteria."""
        logger.info(f"Agent {agent_id} searching tickets with filters: {request.model_dump(exclude_none=True)}")

        try:
            # TODO: Implement full search functionality in TicketSearchService
            # For now, use basic filtering via get_tickets_by_workflow
            filters = {}
            if request.status:
                filters["status"] = request.status
            if request.priority:
                filters["priority"] = request.priority
            if request.assigned_agent_id:
                filters["assigned_agent_id"] = request.assigned_agent_id
            if request.ticket_type:
                filters["ticket_type"] = request.ticket_type

            tickets = await TicketService.get_tickets_by_workflow(
                workflow_id=request.workflow_id or "default",
                filters=filters
            )

            # Simple pagination
            total_count = len(tickets)
            start = request.offset
            end = start + request.limit
            paginated_tickets = tickets[start:end]

            result = {
                "tickets": paginated_tickets,
                "total_count": total_count,
                "limit": request.limit,
                "offset": request.offset,
            }

            return SearchTicketsResponse(**result)

        except ValueError as e:
            logger.error(f"Validation error searching tickets: {e}")
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f"Failed to search tickets: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @router.get("/api/tickets/stats")
    async def get_ticket_stats_endpoint(
        workflow_id: Optional[str] = None,
        agent_id: str = Header(..., alias="X-Agent-ID"),
    ):
        """Get ticket statistics for a workflow."""
        logger.info(f"Agent {agent_id} requesting ticket stats for workflow {workflow_id}")

        try:
            # Auto-detect workflow_id if not provided
            if not workflow_id:
                with get_db() as session:
                    agent = session.query(Agent).filter_by(id=agent_id).first()
                    if agent and agent.current_task_id:
                        task = session.query(Task).filter_by(id=agent.current_task_id).first()
                        if task and task.workflow_id:
                            workflow_id = task.workflow_id

                if not workflow_id:
                    from src.mcp.server import get_single_active_workflow
                    workflow_id = get_single_active_workflow()

                if not workflow_id:
                    raise HTTPException(
                        status_code=400,
                        detail="Could not determine workflow_id"
                    )

            # TODO: Implement TicketStatsService for detailed analytics
            # For now, provide basic stats inline
            tickets = await TicketService.get_tickets_by_workflow(workflow_id)

            stats = {
                "workflow_id": workflow_id,
                "total_tickets": len(tickets),
                "by_status": {},
                "by_priority": {},
                "by_type": {},
            }

            for ticket in tickets:
                # Count by status
                status = ticket.get("status", "unknown")
                stats["by_status"][status] = stats["by_status"].get(status, 0) + 1

                # Count by priority
                priority = ticket.get("priority", "unknown")
                stats["by_priority"][priority] = stats["by_priority"].get(priority, 0) + 1

                # Count by type
                ticket_type = ticket.get("ticket_type", "unknown")
                stats["by_type"][ticket_type] = stats["by_type"].get(ticket_type, 0) + 1

            return stats

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to get ticket stats: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @router.get("/api/workflows/{workflow_id}/tickets", response_model=GetTicketsResponse)
    async def get_tickets_endpoint(
        workflow_id: str,
        status: Optional[str] = None,
        ticket_type: Optional[str] = None,
        priority: Optional[str] = None,
        assigned_agent_id: Optional[str] = None,
        agent_id: str = Header(..., alias="X-Agent-ID"),
    ):
        """Get all tickets for a workflow with optional filtering."""
        logger.info(f"Agent {agent_id} listing tickets for workflow {workflow_id}")

        try:
            filters = {}
            if status:
                filters["status"] = status
            if ticket_type:
                filters["ticket_type"] = ticket_type
            if priority:
                filters["priority"] = priority
            if assigned_agent_id:
                filters["assigned_agent_id"] = assigned_agent_id

            tickets = await TicketService.get_tickets_by_workflow(
                workflow_id=workflow_id,
                filters=filters
            )

            return GetTicketsResponse(
                tickets=tickets,
                workflow_id=workflow_id,
                total_count=len(tickets),
            )

        except ValueError as e:
            logger.error(f"Validation error listing tickets: {e}")
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f"Failed to list tickets: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @router.post("/api/tickets/resolve", response_model=ResolveTicketResponse)
    async def resolve_ticket_endpoint(
        request: ResolveTicketRequest,
        agent_id: str = Header(..., alias="X-Agent-ID"),
    ):
        """Mark a ticket as resolved with notes."""
        logger.info(f"Agent {agent_id} resolving ticket {request.ticket_id}")

        try:
            result = await TicketService.change_status(
                ticket_id=request.ticket_id,
                agent_id=agent_id,
                new_status=request.new_status,
                resolution_notes=request.resolution_notes,
            )

            # Broadcast update
            await server_state.broadcast_update({
                "type": "ticket_resolved",
                "ticket_id": request.ticket_id,
                "agent_id": agent_id,
                "status": request.new_status,
            })

            return ResolveTicketResponse(
                ticket_id=request.ticket_id,
                status=request.new_status,
                message=result["message"],
            )

        except ValueError as e:
            logger.error(f"Validation error resolving ticket: {e}")
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f"Failed to resolve ticket: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @router.post("/api/tickets/link-commit", response_model=LinkCommitResponse)
    async def link_commit_endpoint(
        request: LinkCommitRequest,
        agent_id: str = Header(..., alias="X-Agent-ID"),
    ):
        """Link a git commit to a ticket."""
        logger.info(f"Agent {agent_id} linking commit {request.commit_hash} to ticket {request.ticket_id}")

        try:
            result = await TicketService.link_commit(
                ticket_id=request.ticket_id,
                agent_id=agent_id,
                commit_sha=request.commit_hash,  # Service expects commit_sha, not commit_hash
                commit_message=request.commit_message,
                repository_url=request.repository_url,
            )

            # Broadcast update
            await server_state.broadcast_update({
                "type": "commit_linked_to_ticket",
                "ticket_id": request.ticket_id,
                "agent_id": agent_id,
                "commit_hash": request.commit_hash,
            })

            return LinkCommitResponse(**result)

        except ValueError as e:
            logger.error(f"Validation error linking commit: {e}")
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f"Failed to link commit: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @router.post("/api/tickets/request-clarification", response_model=RequestTicketClarificationResponse)
    async def request_ticket_clarification_endpoint(
        request: RequestTicketClarificationRequest,
        agent_id: str = Header(..., alias="X-Agent-ID"),
    ):
        """Request clarification on a ticket from the workflow owner."""
        logger.info(f"Agent {agent_id} requesting clarification on ticket {request.ticket_id}")

        try:
            result = await TicketService.request_clarification(
                ticket_id=request.ticket_id,
                agent_id=agent_id,
                clarification_request=request.clarification_request,
                block_ticket=request.block_ticket,
            )

            # Broadcast update
            await server_state.broadcast_update({
                "type": "clarification_requested",
                "ticket_id": request.ticket_id,
                "agent_id": agent_id,
                "clarification_request_id": result["clarification_request_id"],
            })

            return RequestTicketClarificationResponse(**result)

        except ValueError as e:
            logger.error(f"Validation error requesting clarification: {e}")
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f"Failed to request clarification: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @router.get("/api/commits/{commit_hash}/diff")
    async def get_commit_diff_endpoint(
        commit_hash: str,
        repository_url: Optional[str] = None,
        agent_id: str = Header(..., alias="X-Agent-ID"),
    ):
        """Get the diff for a specific commit."""
        logger.info(f"Agent {agent_id} requesting diff for commit {commit_hash}")

        try:
            # TODO: Implement GitService for git operations
            # For now, return not implemented error
            raise HTTPException(
                status_code=501,
                detail="Git diff functionality not yet implemented. TODO: Create c2_git_service module"
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to get commit diff: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    return router
