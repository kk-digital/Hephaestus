"""Database models and schema for Hephaestus."""

# REFACTORING NOTE: This file will be split during three-layer architecture refactoring
# See tasks/251104-task-19-file-mapping.txt for complete split plan
#
# DESTINATION MAPPING:
# - Lines 1-25 (Base, imports) → c1_database_session/base.py
# - Lines 27-65 (Agent model) → c1_agent_models/agent_models.py
# - Lines 67-143 (Task model) → c1_task_models/task_models.py
# - Lines 145-170 (Memory model) → c1_memory_models/memory_models.py
# - Lines 172-194 (AgentLog model) → c1_agent_models/agent_models.py
# - Lines 196-206 (ProjectContext model) → c1_workflow_models/workflow_models.py
# - Lines 208-233 (Workflow model) → c1_workflow_models/workflow_models.py
# - Lines 235-258 (Phase model) → c1_workflow_models/workflow_models.py
# - Lines 260-280 (PhaseExecution model) → c1_workflow_models/workflow_models.py
# - Lines 282-319 (AgentWorktree model) → c1_agent_models/agent_models.py
# - Lines 321-351 (WorktreeCommit model) → c1_agent_models/agent_models.py
# - Lines 353-371 (ValidationReview model) → c1_validation_models/validation_models.py
# - Lines 373-401 (MergeConflictResolution model) → c1_workflow_models/workflow_models.py
# - Lines 403-435 (AgentResult model) → c1_agent_models/agent_models.py
# - Lines 437-463 (WorkflowResult model) → c1_workflow_models/workflow_models.py
# - Lines 465-495 (GuardianAnalysis model) → c1_monitoring_models/monitoring_models.py
# - Lines 497-519 (ConductorAnalysis model) → c1_monitoring_models/monitoring_models.py
# - Lines 521-538 (DetectedDuplicate model) → c1_monitoring_models/monitoring_models.py
# - Lines 540-556 (SteeringIntervention model) → c1_monitoring_models/monitoring_models.py
# - Lines 558-596 (DiagnosticRun model) → c1_monitoring_models/monitoring_models.py
# - Lines 598-657 (Ticket model) → c1_ticket_models/ticket_models.py
# - Lines 659-686 (TicketComment model) → c1_ticket_models/ticket_models.py
# - Lines 688-715 (TicketHistory model) → c1_ticket_models/ticket_models.py
# - Lines 717-744 (TicketCommit model) → c1_ticket_models/ticket_models.py
# - Lines 746-775 (BoardConfig model) → c1_ticket_models/ticket_models.py
# - Lines 777-965 (DatabaseManager class) → c1_database_session/database_manager.py
# - Lines 967-987 (get_db function) → c1_database_session/session.py

import os
import logging
from datetime import datetime
from typing import Optional
from sqlalchemy import (
    create_engine,
    Column,
    String,
    Text,
    Integer,
    Float,
    DateTime,
    ForeignKey,
    CheckConstraint,
    JSON,
    Boolean,
)
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy.pool import StaticPool

# Import Base from new c1 layer (shared base for all models)
from src.c1_database_session.base import Base, logger

# Import Agent models from new c1 layer (strangler fig pattern)
from src.c1_agent_models.agent import Agent, AgentLog, AgentWorktree, WorktreeCommit, AgentResult  # noqa: E402

# Import Task model from new c1 layer
from src.c1_task_models.task import Task  # noqa: E402

# Import Memory model from new c1 layer
from src.c1_memory_models.memory import Memory  # noqa: E402

# Import Workflow models from new c1 layer
from src.c1_workflow_models.workflow import (  # noqa: E402
    ProjectContext, Workflow, Phase, PhaseExecution,
    ValidationReview, MergeConflictResolution, WorkflowResult
)

# Import Monitoring models from new c1 layer
from src.c1_monitoring_models.monitoring import (  # noqa: E402
    GuardianAnalysis, ConductorAnalysis, DetectedDuplicate,
    SteeringIntervention, DiagnosticRun
)

# Import Ticket models from new c1 layer
from src.c1_ticket_models.ticket import (  # noqa: E402
    Ticket, TicketComment, TicketHistory, TicketCommit, BoardConfig
)













class DatabaseManager:
    """Manager for database operations."""

    def __init__(self, database_path: str = "hephaestus.db"):
        """Initialize database connection."""
        self.database_path = database_path
        self.engine = create_engine(
            f"sqlite:///{database_path}",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            echo=False,
        )
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

    def create_tables(self):
        """Create all database tables."""
        Base.metadata.create_all(bind=self.engine)

        # Create FTS5 virtual table for ticket search
        self._create_fts5_tables()

        # Create indexes for performance optimization
        self._create_indexes()

    def _create_fts5_tables(self):
        """Create FTS5 virtual tables and triggers for ticket search."""
        try:
            with self.engine.connect() as conn:
                # Create FTS5 virtual table for tickets
                conn.execute(
                    text(
                        """
                    CREATE VIRTUAL TABLE IF NOT EXISTS ticket_fts USING fts5(
                        ticket_id UNINDEXED,
                        title,
                        description,
                        tags
                    )
                """
                    )
                )

                # Create triggers to keep FTS5 in sync with tickets table
                # Trigger for INSERT
                conn.execute(
                    text(
                        """
                    CREATE TRIGGER IF NOT EXISTS tickets_fts_insert AFTER INSERT ON tickets BEGIN
                        INSERT INTO ticket_fts(ticket_id, title, description, tags)
                        VALUES (new.id, new.title, new.description,
                                COALESCE(json_extract(new.tags, '$'), ''));
                    END
                """
                    )
                )

                # Trigger for UPDATE
                conn.execute(
                    text(
                        """
                    CREATE TRIGGER IF NOT EXISTS tickets_fts_update AFTER UPDATE ON tickets BEGIN
                        DELETE FROM ticket_fts WHERE ticket_id = old.id;
                        INSERT INTO ticket_fts(ticket_id, title, description, tags)
                        VALUES (new.id, new.title, new.description,
                                COALESCE(json_extract(new.tags, '$'), ''));
                    END
                """
                    )
                )

                # Trigger for DELETE
                conn.execute(
                    text(
                        """
                    CREATE TRIGGER IF NOT EXISTS tickets_fts_delete AFTER DELETE ON tickets BEGIN
                        DELETE FROM ticket_fts WHERE ticket_id = old.id;
                    END
                """
                    )
                )

                conn.commit()
                logger.info("Created FTS5 virtual table and triggers for ticket search")
        except Exception as e:
            logger.debug(f"FTS5 table setup (may already exist): {e}")

    def _create_indexes(self):
        """Create database indexes for performance optimization."""
        try:
            with self.engine.connect() as conn:
                # Tickets table indexes
                conn.execute(
                    text(
                        """
                    CREATE INDEX IF NOT EXISTS idx_tickets_workflow_status
                    ON tickets(workflow_id, status)
                """
                    )
                )

                conn.execute(
                    text(
                        """
                    CREATE INDEX IF NOT EXISTS idx_tickets_workflow_priority
                    ON tickets(workflow_id, priority)
                """
                    )
                )

                conn.execute(
                    text(
                        """
                    CREATE INDEX IF NOT EXISTS idx_tickets_assigned_agent
                    ON tickets(assigned_agent_id)
                """
                    )
                )

                conn.execute(
                    text(
                        """
                    CREATE INDEX IF NOT EXISTS idx_tickets_created_at
                    ON tickets(created_at)
                """
                    )
                )

                # Ticket comments index
                conn.execute(
                    text(
                        """
                    CREATE INDEX IF NOT EXISTS idx_ticket_comments_ticket_id
                    ON ticket_comments(ticket_id)
                """
                    )
                )

                # Ticket history index
                conn.execute(
                    text(
                        """
                    CREATE INDEX IF NOT EXISTS idx_ticket_history_ticket_id
                    ON ticket_history(ticket_id)
                """
                    )
                )

                # Ticket commits index
                conn.execute(
                    text(
                        """
                    CREATE INDEX IF NOT EXISTS idx_ticket_commits_ticket_id
                    ON ticket_commits(ticket_id)
                """
                    )
                )

                conn.execute(
                    text(
                        """
                    CREATE INDEX IF NOT EXISTS idx_ticket_commits_sha
                    ON ticket_commits(commit_sha)
                """
                    )
                )

                # Tasks table indexes for ticket tracking
                conn.execute(
                    text(
                        """
                    CREATE INDEX IF NOT EXISTS idx_tasks_ticket_id
                    ON tasks(ticket_id)
                """
                    )
                )

                conn.commit()
                logger.info("Created performance indexes for ticket tracking system")
        except Exception as e:
            logger.debug(f"Index creation (may already exist): {e}")

    def get_session(self):
        """Get a database session."""
        return self.SessionLocal()

    def drop_tables(self):
        """Drop all database tables (for testing)."""
        Base.metadata.drop_all(bind=self.engine)


# Context manager for database sessions
from contextlib import contextmanager
from sqlalchemy.sql import text


@contextmanager
def get_db(database_path: Optional[str] = None):
    """Provide a transactional scope around a series of operations."""
    if database_path is None:
        # Check environment variable for test database
        database_path = os.environ.get("HEPHAESTUS_TEST_DB", "hephaestus.db")
    db_manager = DatabaseManager(database_path)
    db = db_manager.get_session()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
