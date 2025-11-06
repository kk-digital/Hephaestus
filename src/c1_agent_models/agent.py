"""CodeAgent-related models for Hephaestus (managed AI coding agent instances)."""

from datetime import datetime
from sqlalchemy import Column, String, Text, Integer, DateTime, ForeignKey, CheckConstraint, Boolean, JSON
from sqlalchemy.orm import relationship

from src.c1_database_session.base import Base


class CodeAgent(Base):
    """CodeAgent model representing a managed AI coding agent instance."""

    __tablename__ = "code_agents"

    id = Column(String, primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    system_prompt = Column(Text, nullable=False)
    status = Column(
        String,
        CheckConstraint("status IN ('idle', 'working', 'stuck', 'terminated')"),
        default="idle",
        nullable=False,
    )
    cli_type = Column(String, nullable=False)  # claude, codex, etc.
    tmux_session_name = Column(String, unique=True)
    current_task_id = Column(String, ForeignKey("tasks.id"))
    last_activity = Column(DateTime, default=datetime.utcnow)
    health_check_failures = Column(Integer, default=0)

    # Validation-related fields
    agent_type = Column(
        String,
        CheckConstraint(
            "agent_type IN ('phase', 'validator', 'result_validator', 'monitor', 'diagnostic')"
        ),
        default="phase",
        nullable=False,
    )
    kept_alive_for_validation = Column(Boolean, default=False)

    # Relationships
    created_tasks = relationship(
        "Task", back_populates="created_by_code_agent", foreign_keys="Task.created_by_agent_id"
    )
    assigned_tasks = relationship("Task", foreign_keys="Task.assigned_agent_id")
    memories = relationship("Memory", back_populates="code_agent")
    logs = relationship("CodeAgentLog", back_populates="code_agent")


class CodeAgentLog(Base):
    """Log entries for code agent activities and interventions."""

    __tablename__ = "code_agent_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_at = Column(
        DateTime, default=datetime.utcnow, nullable=False
    )  # Added for compatibility
    code_agent_id = Column(
        String, ForeignKey("code_agents.id"), nullable=True
    )  # Made nullable for conductor logs
    log_type = Column(
        String,
        nullable=False,
    )  # Removed constraint to allow more types
    message = Column(Text)
    details = Column(JSON)  # Additional structured data

    # Relationships
    code_agent = relationship("CodeAgent", back_populates="logs")


class CodeAgentWorktree(Base):
    """Track git worktree isolation for code agents."""

    __tablename__ = "code_agent_worktrees"

    code_agent_id = Column(String, ForeignKey("code_agents.id"), primary_key=True)
    worktree_path = Column(Text, nullable=False)
    branch_name = Column(String, unique=True, nullable=False)
    parent_code_agent_id = Column(String, ForeignKey("code_agents.id"))
    parent_commit_sha = Column(String, nullable=False)
    base_commit_sha = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    merged_at = Column(DateTime)
    merge_status = Column(
        String,
        CheckConstraint("merge_status IN ('active', 'merged', 'abandoned', 'cleaned')"),
        default="active",
        nullable=False,
    )
    merge_commit_sha = Column(String)
    disk_usage_mb = Column(Integer)

    # Relationships
    code_agent = relationship("CodeAgent", foreign_keys=[code_agent_id], backref="worktree")
    parent_code_agent = relationship("CodeAgent", foreign_keys=[parent_code_agent_id])
    commits = relationship(
        "WorktreeCommit",
        back_populates="worktree",
        foreign_keys="WorktreeCommit.code_agent_id",
        primaryjoin="CodeAgentWorktree.code_agent_id==WorktreeCommit.code_agent_id",
    )
    conflict_resolutions = relationship(
        "MergeConflictResolution",
        back_populates="worktree",
        foreign_keys="MergeConflictResolution.code_agent_id",
        primaryjoin="CodeAgentWorktree.code_agent_id==MergeConflictResolution.code_agent_id",
    )


class WorktreeCommit(Base):
    """Track commits within code agent worktrees for traceability."""

    __tablename__ = "worktree_commits"

    id = Column(String, primary_key=True)
    code_agent_id = Column(String, ForeignKey("code_agents.id"), nullable=False)
    commit_sha = Column(String, unique=True, nullable=False)
    commit_type = Column(
        String,
        CheckConstraint(
            "commit_type IN ('parent_checkpoint', 'validation_ready', 'final', 'auto_save', 'conflict_resolution')"
        ),
        nullable=False,
    )
    commit_message = Column(Text, nullable=False)
    files_changed = Column(Integer)
    insertions = Column(Integer)
    deletions = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    code_agent = relationship("CodeAgent", backref="worktree_commits", overlaps="commits")
    worktree = relationship(
        "CodeAgentWorktree",
        back_populates="commits",
        foreign_keys=[code_agent_id],
        primaryjoin="WorktreeCommit.code_agent_id==CodeAgentWorktree.code_agent_id",
        overlaps="code_agent,worktree_commits",
    )


class CodeAgentResult(Base):
    """Store formal results reported by code agents for their completed tasks."""

    __tablename__ = "code_agent_results"

    id = Column(String, primary_key=True)
    code_agent_id = Column(String, ForeignKey("code_agents.id"), nullable=False)
    task_id = Column(String, ForeignKey("tasks.id"), nullable=False)
    markdown_content = Column(Text, nullable=False)
    markdown_file_path = Column(Text, nullable=False)
    result_type = Column(
        String,
        CheckConstraint(
            "result_type IN ('implementation', 'analysis', 'fix', 'design', 'test', 'documentation')"
        ),
        nullable=False,
    )
    summary = Column(Text, nullable=False)
    verification_status = Column(
        String,
        CheckConstraint("verification_status IN ('unverified', 'verified', 'disputed')"),
        default="unverified",
        nullable=False,
    )
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    verified_at = Column(DateTime)
    verified_by_validation_id = Column(String, ForeignKey("validation_reviews.id"))

    # Relationships
    code_agent = relationship("CodeAgent", backref="results")
    task = relationship("Task", back_populates="results")
    validation_review = relationship("ValidationReview", backref="verified_results")
