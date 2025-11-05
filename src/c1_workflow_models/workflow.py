"""Workflow-related models for Hephaestus."""

from datetime import datetime
from sqlalchemy import Column, String, Text, Integer, DateTime, ForeignKey, CheckConstraint, JSON, Boolean, Float
from sqlalchemy.orm import relationship

from src.c1_database_session.base import Base


class ProjectContext(Base):
    """Project-wide context and configuration."""

    __tablename__ = "project_context"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String, unique=True, nullable=False)
    value = Column(JSON, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    description = Column(Text)


class Workflow(Base):
    """Workflow model representing a collection of phases."""

    __tablename__ = "workflows"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    phases_folder_path = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    status = Column(
        String,
        CheckConstraint("status IN ('active', 'completed', 'paused', 'failed')"),
        default="active",
        nullable=False,
    )

    # Result tracking fields
    result_found = Column(Boolean, default=False)
    result_id = Column(String, ForeignKey("workflow_results.id"))
    completed_by_result = Column(Boolean, default=False)

    # Relationships
    phases = relationship("Phase", back_populates="workflow", order_by="Phase.order")
    result = relationship("WorkflowResult", foreign_keys=[result_id])
    all_results = relationship("WorkflowResult", foreign_keys="WorkflowResult.workflow_id")


class Phase(Base):
    """Phase model representing a workflow phase."""

    __tablename__ = "phases"

    id = Column(String, primary_key=True)
    workflow_id = Column(String, ForeignKey("workflows.id"), nullable=False)
    order = Column(Integer, nullable=False)  # From XX_ prefix
    name = Column(String, nullable=False)  # From filename
    description = Column(Text, nullable=False)
    done_definitions = Column(JSON, nullable=False)  # List of criteria
    additional_notes = Column(Text)
    outputs = Column(Text)  # Expected outputs description
    next_steps = Column(Text)  # Instructions for next phase
    working_directory = Column(String)  # Default working directory for agents in this phase

    # Validation configuration
    validation = Column(JSON)  # Stores validation criteria and settings

    # Relationships
    workflow = relationship("Workflow", back_populates="phases")
    tasks = relationship("Task", back_populates="phase")
    executions = relationship("PhaseExecution", back_populates="phase")


class PhaseExecution(Base):
    """Track execution of phases."""

    __tablename__ = "phase_executions"

    id = Column(String, primary_key=True)
    phase_id = Column(String, ForeignKey("phases.id"), nullable=False)
    workflow_execution_id = Column(String)  # For tracking multiple workflow runs
    status = Column(
        String,
        CheckConstraint("status IN ('pending', 'in_progress', 'completed', 'failed', 'skipped')"),
        default="pending",
        nullable=False,
    )
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    completion_summary = Column(Text)

    # Relationships
    phase = relationship("Phase", back_populates="executions")


class ValidationReview(Base):
    """Track validation reviews for tasks."""

    __tablename__ = "validation_reviews"

    id = Column(String, primary_key=True)
    task_id = Column(String, ForeignKey("tasks.id"), nullable=False)
    validator_agent_id = Column(String, ForeignKey("agents.id"), nullable=False)
    iteration_number = Column(Integer, nullable=False)
    validation_passed = Column(Boolean, nullable=False)
    feedback = Column(Text, nullable=False)
    evidence = Column(JSON)  # Array of evidence items
    recommendations = Column(JSON)  # Array of follow-up tasks
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    task = relationship("Task", backref="validation_reviews")
    validator_agent = relationship("Agent", backref="validation_reviews")


class MergeConflictResolution(Base):
    """Track automatic conflict resolutions during merges."""

    __tablename__ = "merge_conflict_resolutions"

    id = Column(String, primary_key=True)
    agent_id = Column(String, ForeignKey("agents.id"), nullable=False)
    file_path = Column(Text, nullable=False)
    parent_modified_at = Column(DateTime)
    child_modified_at = Column(DateTime)
    resolution_choice = Column(
        String,
        CheckConstraint("resolution_choice IN ('parent', 'child', 'tie_child')"),
        nullable=False,
    )
    resolved_at = Column(DateTime, default=datetime.utcnow)
    commit_sha = Column(String, ForeignKey("worktree_commits.commit_sha"))

    # Relationships
    agent = relationship("Agent", backref="conflict_resolutions", overlaps="conflict_resolutions")
    worktree = relationship(
        "AgentWorktree",
        back_populates="conflict_resolutions",
        foreign_keys=[agent_id],
        primaryjoin="MergeConflictResolution.agent_id==AgentWorktree.agent_id",
        overlaps="agent,conflict_resolutions",
    )
    commit = relationship("WorktreeCommit", backref="resolutions")


class WorkflowResult(Base):
    """Store workflow-level results with evidence and validation status."""

    __tablename__ = "workflow_results"

    id = Column(String, primary_key=True)
    workflow_id = Column(String, ForeignKey("workflows.id"), nullable=False)
    agent_id = Column(String, ForeignKey("agents.id"), nullable=False)
    result_file_path = Column(Text, nullable=False)
    result_content = Column(Text, nullable=False)
    status = Column(
        String,
        CheckConstraint("status IN ('pending_validation', 'validated', 'rejected')"),
        default="pending_validation",
        nullable=False,
    )
    validation_feedback = Column(Text)
    validation_evidence = Column(JSON)
    validated_by_agent_id = Column(String, ForeignKey("agents.id"))
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    validated_at = Column(DateTime)

    # Relationships
    workflow = relationship("Workflow", foreign_keys=[workflow_id], back_populates="all_results")
    agent = relationship("Agent", foreign_keys=[agent_id], backref="workflow_results")
    validator_agent = relationship("Agent", foreign_keys=[validated_by_agent_id])
