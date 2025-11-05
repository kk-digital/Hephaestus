"""Task model for Hephaestus."""

from datetime import datetime
from sqlalchemy import Column, String, Text, Integer, Float, DateTime, ForeignKey, CheckConstraint, JSON, Boolean
from sqlalchemy.orm import relationship

from src.c1_database_session.base import Base


class Task(Base):
    """Task model representing work to be done."""

    __tablename__ = "tasks"

    id = Column(String, primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    raw_description = Column(Text, nullable=False)
    enriched_description = Column(Text)
    done_definition = Column(Text, nullable=False)
    status = Column(
        String,
        CheckConstraint(
            "status IN ('pending', 'queued', 'blocked', 'assigned', 'in_progress', 'under_review', 'validation_in_progress', 'needs_work', 'done', 'failed', 'duplicated')"
        ),
        default="pending",
        nullable=False,
    )
    priority = Column(
        String,
        CheckConstraint("priority IN ('low', 'medium', 'high')"),
        default="medium",
    )
    assigned_agent_id = Column(String, ForeignKey("agents.id"))
    parent_task_id = Column(String, ForeignKey("tasks.id"))
    created_by_agent_id = Column(String, ForeignKey("agents.id"))
    phase_id = Column(String, ForeignKey("phases.id"))  # Phase this task belongs to
    workflow_id = Column(String, ForeignKey("workflows.id"))  # Workflow this task is part of
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    completion_notes = Column(Text)
    failure_reason = Column(Text)
    estimated_complexity = Column(Integer)

    # Validation-related fields
    review_done = Column(Boolean, default=False)
    validation_enabled = Column(Boolean, default=False)
    validation_iteration = Column(Integer, default=0)
    last_validation_feedback = Column(Text)

    # Results tracking
    has_results = Column(Boolean, default=False)

    # Task deduplication fields
    embedding = Column(JSON)  # Store embedding vector as list of floats
    related_task_ids = Column(JSON)  # List of related task IDs
    duplicate_of_task_id = Column(String, ForeignKey("tasks.id"))
    similarity_score = Column(Float)  # Similarity score to duplicate_of task

    # Queue management fields
    queued_at = Column(DateTime)  # When task was queued
    queue_position = Column(Integer)  # Position in queue (for UI display)
    priority_boosted = Column(Boolean, default=False)  # If manually boosted to bypass queue

    # Ticket tracking integration
    ticket_id = Column(
        String, ForeignKey("tickets.id")
    )  # Associated ticket (required when ticket tracking enabled)
    related_ticket_ids = Column(JSON)  # List of related ticket IDs for context

    # Relationships
    assigned_agent = relationship("Agent", foreign_keys=[assigned_agent_id])
    duplicate_of = relationship(
        "Task", remote_side=[id], foreign_keys=[duplicate_of_task_id], post_update=True
    )
    parent_task = relationship(
        "Task", remote_side=[id], foreign_keys=[parent_task_id], backref="subtasks"
    )
    created_by_agent = relationship(
        "Agent", back_populates="created_tasks", foreign_keys=[created_by_agent_id]
    )
    memories = relationship("Memory", back_populates="task")
    phase = relationship("Phase", back_populates="tasks")
    workflow = relationship("Workflow", backref="tasks")
    results = relationship("AgentResult", back_populates="task")
    ticket = relationship("Ticket", backref="related_tasks")
