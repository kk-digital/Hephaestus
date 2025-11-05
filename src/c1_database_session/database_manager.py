"""Database manager and session utilities for Hephaestus."""

import os
import logging
from typing import Optional
from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.sql import text

from src.c1_database_session.base import Base

logger = logging.getLogger(__name__)


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
