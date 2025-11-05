"""Monitoring-related models for Hephaestus."""

from datetime import datetime
from sqlalchemy import Column, String, Text, Integer, Float, DateTime, ForeignKey, JSON, Boolean, CheckConstraint
from sqlalchemy.orm import relationship

from src.c1_database_session.base import Base


class GuardianAnalysis(Base):
    """Dedicated table for Guardian trajectory analyses."""

    __tablename__ = "guardian_analyses"

    id = Column(Integer, primary_key=True)
    agent_id = Column(String, ForeignKey("agents.id"), nullable=False, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Trajectory analysis fields
    current_phase = Column(String)
    trajectory_aligned = Column(Boolean)
    alignment_score = Column(Float, index=True)
    needs_steering = Column(Boolean, index=True)
    steering_type = Column(String)
    steering_recommendation = Column(Text)
    trajectory_summary = Column(Text)
    last_claude_message_marker = Column(String(100))  # NEW: Marker for next cycle to identify new content

    # Accumulated context fields
    accumulated_goal = Column(Text)
    current_focus = Column(String)
    session_duration = Column(String)
    conversation_length = Column(Integer)

    # Full analysis details as JSON for reference
    details = Column(JSON)

    # Relationships
    agent = relationship("Agent", backref="guardian_analyses", overlaps="logs")


class ConductorAnalysis(Base):
    """Dedicated table for Conductor system analyses."""

    __tablename__ = "conductor_analyses"

    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)

    # System coherence fields
    coherence_score = Column(Float, index=True)
    num_agents = Column(Integer)
    system_status = Column(Text)

    # Duplicate detection
    duplicate_count = Column(Integer)

    # Decision counts
    termination_count = Column(Integer)
    coordination_count = Column(Integer)

    # Full analysis as JSON
    details = Column(JSON)


class DetectedDuplicate(Base):
    """Table for tracking detected duplicate work."""

    __tablename__ = "detected_duplicates"

    id = Column(Integer, primary_key=True)
    conductor_analysis_id = Column(Integer, ForeignKey("conductor_analyses.id"))
    agent1_id = Column(String, ForeignKey("agents.id"))
    agent2_id = Column(String, ForeignKey("agents.id"))
    similarity_score = Column(Float)
    work_description = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)

    # Relationships
    conductor_analysis = relationship("ConductorAnalysis", backref="duplicates")
    agent1 = relationship("Agent", foreign_keys=[agent1_id], backref="duplicates_as_agent1")
    agent2 = relationship("Agent", foreign_keys=[agent2_id], backref="duplicates_as_agent2")


class SteeringIntervention(Base):
    """Table for tracking steering interventions."""

    __tablename__ = "steering_interventions"

    id = Column(Integer, primary_key=True)
    agent_id = Column(String, ForeignKey("agents.id"), nullable=False)
    guardian_analysis_id = Column(Integer, ForeignKey("guardian_analyses.id"))
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    steering_type = Column(String)
    message = Column(Text)
    was_successful = Column(Boolean)

    # Relationships
    agent = relationship("Agent", backref="interventions")
    guardian_analysis = relationship("GuardianAnalysis", backref="interventions")


class DiagnosticRun(Base):
    """Track diagnostic agent executions for workflow stuck detection."""

    __tablename__ = "diagnostic_runs"

    id = Column(String, primary_key=True)
    workflow_id = Column(String, ForeignKey("workflows.id"), nullable=False)
    diagnostic_agent_id = Column(String, ForeignKey("agents.id"))
    diagnostic_task_id = Column(String, ForeignKey("tasks.id"))

    # Trigger conditions
    triggered_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    total_tasks_at_trigger = Column(Integer, nullable=False)
    done_tasks_at_trigger = Column(Integer, nullable=False)
    failed_tasks_at_trigger = Column(Integer, nullable=False)
    time_since_last_task_seconds = Column(Integer, nullable=False)

    # Results
    tasks_created_count = Column(Integer, default=0)
    tasks_created_ids = Column(JSON)  # List of task IDs created
    completed_at = Column(DateTime)
    status = Column(
        String,
        CheckConstraint("status IN ('created', 'running', 'completed', 'failed')"),
        default="created",
        nullable=False,
    )

    # Analysis context snapshot
    workflow_goal = Column(Text)
    phases_analyzed = Column(JSON)  # List of phase info
    agents_reviewed = Column(JSON)  # List of agent summaries
    diagnosis = Column(Text)  # What the diagnostic agent concluded

    # Relationships
    workflow = relationship("Workflow", backref="diagnostic_runs")
    agent = relationship("Agent", foreign_keys=[diagnostic_agent_id], backref="diagnostic_runs")
    task = relationship("Task", foreign_keys=[diagnostic_task_id], backref="diagnostic_runs")
