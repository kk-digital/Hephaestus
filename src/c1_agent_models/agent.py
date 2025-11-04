"""Agent-related models for Hephaestus."""

from datetime import datetime
from sqlalchemy import Column, String, Text, Integer, DateTime, ForeignKey, CheckConstraint, Boolean, JSON
from sqlalchemy.orm import relationship

from src.c1_database_session.base import Base


class Agent(Base):
    """Agent model representing an AI agent instance."""

    __tablename__ = "agents"

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
        "Task", back_populates="created_by_agent", foreign_keys="Task.created_by_agent_id"
    )
    assigned_tasks = relationship("Task", foreign_keys="Task.assigned_agent_id")
    memories = relationship("Memory", back_populates="agent")
    logs = relationship("AgentLog", back_populates="agent")


class AgentLog(Base):
    """Log entries for agent activities and interventions."""

    __tablename__ = "agent_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_at = Column(
        DateTime, default=datetime.utcnow, nullable=False
    )  # Added for compatibility
    agent_id = Column(
        String, ForeignKey("agents.id"), nullable=True
    )  # Made nullable for conductor logs
    log_type = Column(
        String,
        nullable=False,
    )  # Removed constraint to allow more types
    message = Column(Text)
    details = Column(JSON)  # Additional structured data

    # Relationships
    agent = relationship("Agent", back_populates="logs")
