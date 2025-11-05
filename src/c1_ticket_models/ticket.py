"""Ticket-related models for Hephaestus."""

from datetime import datetime
from sqlalchemy import Column, String, Text, Integer, DateTime, ForeignKey, CheckConstraint, JSON, Boolean
from sqlalchemy.orm import relationship

from src.c1_database_session.base import Base


class Ticket(Base):
    """Ticket model for ticket tracking system."""

    __tablename__ = "tickets"

    id = Column(String, primary_key=True)  # Format: ticket-{uuid}
    workflow_id = Column(String, ForeignKey("workflows.id"), nullable=False)
    created_by_agent_id = Column(String, ForeignKey("agents.id"), nullable=False)
    assigned_agent_id = Column(String, ForeignKey("agents.id"))

    # Core Fields
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=False)
    ticket_type = Column(String(50), nullable=False)  # bug, feature, improvement, task, spike, etc.
    priority = Column(String(20), nullable=False)  # low, medium, high, critical
    status = Column(
        String(50), nullable=False
    )  # Based on board_config columns (fully configurable)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    started_at = Column(DateTime)  # When work begins
    completed_at = Column(DateTime)  # When marked complete

    # Links & References
    parent_ticket_id = Column(String, ForeignKey("tickets.id"))
    related_task_ids = Column(JSON)  # List of related task IDs
    related_ticket_ids = Column(JSON)  # List of related ticket IDs for context
    tags = Column(JSON)  # List of tags

    # Search & Discovery
    embedding = Column(JSON)  # Cached embedding for quick access
    embedding_id = Column(String)  # Reference to Qdrant

    # Blocking & Dependencies
    blocked_by_ticket_ids = Column(JSON)  # List of ticket IDs blocking this ticket
    is_resolved = Column(Boolean, default=False)  # Whether this ticket is resolved
    resolved_at = Column(DateTime)  # When ticket was resolved

    # Relationships
    workflow = relationship("Workflow", backref="tickets")
    created_by_agent = relationship(
        "Agent", foreign_keys=[created_by_agent_id], backref="created_tickets"
    )
    assigned_agent = relationship(
        "Agent", foreign_keys=[assigned_agent_id], backref="assigned_tickets"
    )
    parent_ticket = relationship(
        "Ticket", remote_side=[id], foreign_keys=[parent_ticket_id], backref="sub_tickets"
    )
    comments = relationship("TicketComment", back_populates="ticket")
    history = relationship("TicketHistory", back_populates="ticket")
    commits = relationship("TicketCommit", back_populates="ticket")

    # Create indexes
    __table_args__ = (
        # Note: Indexes are created separately in create_tables() for better compatibility
    )


class TicketComment(Base):
    """Comments and discussions on tickets."""

    __tablename__ = "ticket_comments"

    id = Column(String, primary_key=True)  # Format: comment-{uuid}
    ticket_id = Column(String, ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False)
    agent_id = Column(String, ForeignKey("agents.id"), nullable=False)

    # Content
    comment_text = Column(Text, nullable=False)
    comment_type = Column(
        String(50), default="general"
    )  # general, status_change, assignment, blocker, resolution

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime)  # If edited
    is_edited = Column(Boolean, default=False)

    # Rich Content
    mentions = Column(JSON)  # List of mentioned agent/ticket IDs
    attachments = Column(JSON)  # List of file paths or URLs

    # Relationships
    ticket = relationship("Ticket", back_populates="comments")
    agent = relationship("Agent", backref="ticket_comments")


class TicketHistory(Base):
    """Track all changes to tickets for audit trail."""

    __tablename__ = "ticket_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticket_id = Column(String, ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False)
    agent_id = Column(String, ForeignKey("agents.id"), nullable=False)

    # Change Information
    change_type = Column(
        String(50), nullable=False
    )  # created, status_changed, assigned, commented, field_updated, commit_linked, reopened, blocked, unblocked
    field_name = Column(String(100))  # Which field changed (if applicable)
    old_value = Column(Text)  # Previous value (JSON for complex types)
    new_value = Column(Text)  # New value (JSON for complex types)

    # Context
    change_description = Column(Text)  # Human-readable description
    change_metadata = Column(JSON)  # Additional context (e.g., commit info, file paths)

    # Timing
    changed_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    ticket = relationship("Ticket", back_populates="history")
    agent = relationship("Agent", backref="ticket_history")


class TicketCommit(Base):
    """Link git commits to tickets for traceability."""

    __tablename__ = "ticket_commits"

    id = Column(String, primary_key=True)  # Format: tc-{uuid}
    ticket_id = Column(String, ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False)
    agent_id = Column(String, ForeignKey("agents.id"), nullable=False)

    # Commit Information
    commit_sha = Column(String(40), nullable=False)
    commit_message = Column(Text, nullable=False)
    commit_timestamp = Column(DateTime, nullable=False)

    # Change Stats
    files_changed = Column(Integer)
    insertions = Column(Integer)
    deletions = Column(Integer)
    files_list = Column(JSON)  # List of changed file paths

    # Linking
    linked_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    link_method = Column(String(50), default="manual")  # manual, auto_detected, worktree

    # Relationships
    ticket = relationship("Ticket", back_populates="commits")
    agent = relationship("Agent", backref="ticket_commits")


class BoardConfig(Base):
    """Kanban board configurations per workflow."""

    __tablename__ = "board_configs"

    id = Column(String, primary_key=True)  # Format: board-{uuid}
    workflow_id = Column(
        String, ForeignKey("workflows.id", ondelete="CASCADE"), unique=True, nullable=False
    )

    # Board Configuration
    name = Column(String(200), nullable=False)
    columns = Column(JSON, nullable=False)  # Array of {id, name, order, color}
    ticket_types = Column(JSON, nullable=False)  # Array of allowed ticket types
    default_ticket_type = Column(String(50))
    initial_status = Column(String(50), nullable=False)  # Default status for new tickets

    # Settings
    auto_assign = Column(Boolean, default=False)
    require_comments_on_status_change = Column(Boolean, default=False)
    allow_reopen = Column(Boolean, default=True)
    track_time = Column(Boolean, default=False)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    workflow = relationship("Workflow", backref="board_config")
