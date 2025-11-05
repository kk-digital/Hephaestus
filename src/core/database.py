"""Database models and schema for Hephaestus.

This file now serves as a compatibility shim that imports all models
from the new c1 layer modules. All model definitions have been extracted
to appropriate c1 layer packages during three-layer architecture refactoring.
"""

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

# Import User models from new c1 layer
from src.c1_user_models.user import (  # noqa: E402
    User, Role, UserRole, Permission, RolePermission,
    Team, TeamMember, AuthToken, UserSession, AuditLog,
    UserPreferences, LoginAttempt
)

# Import DatabaseManager and get_db from new c1 layer
from src.c1_database_session.database_manager import DatabaseManager, get_db  # noqa: E402


__all__ = [
    # Base
    "Base",
    "logger",
    # Agent models
    "Agent",
    "AgentLog",
    "AgentWorktree",
    "WorktreeCommit",
    "AgentResult",
    # Task model
    "Task",
    # Memory model
    "Memory",
    # Workflow models
    "ProjectContext",
    "Workflow",
    "Phase",
    "PhaseExecution",
    "ValidationReview",
    "MergeConflictResolution",
    "WorkflowResult",
    # Monitoring models
    "GuardianAnalysis",
    "ConductorAnalysis",
    "DetectedDuplicate",
    "SteeringIntervention",
    "DiagnosticRun",
    # Ticket models
    "Ticket",
    "TicketComment",
    "TicketHistory",
    "TicketCommit",
    "BoardConfig",
    # User models
    "User",
    "Role",
    "UserRole",
    "Permission",
    "RolePermission",
    "Team",
    "TeamMember",
    "AuthToken",
    "UserSession",
    "AuditLog",
    "UserPreferences",
    "LoginAttempt",
    # Database utilities
    "DatabaseManager",
    "get_db",
]
