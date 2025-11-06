"""Memory model for Hephaestus (agent discoveries and learnings)."""

from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, CheckConstraint, JSON
from sqlalchemy.orm import relationship

from src.c1_database_session.base import Base


class Memory(Base):
    """Memory model for storing agent discoveries and learnings."""

    __tablename__ = "memories"

    id = Column(String, primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    agent_id = Column(String, ForeignKey("agents.id"), nullable=False)
    content = Column(Text, nullable=False)
    memory_type = Column(
        String,
        CheckConstraint(
            "memory_type IN ('error_fix', 'discovery', 'decision', 'learning', 'warning', 'codebase_knowledge')"
        ),
        nullable=False,
    )
    embedding_id = Column(String)  # Reference to vector store
    related_task_id = Column(String, ForeignKey("tasks.id"))
    tags = Column(JSON)  # JSON array of tags
    related_files = Column(JSON)  # JSON array of file paths
    extra_data = Column(JSON)  # Additional metadata (renamed from metadata)

    # Relationships
    agent = relationship("Agent", back_populates="memories")
    task = relationship("Task", back_populates="memories")
