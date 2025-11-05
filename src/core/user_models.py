"""User models - DEPRECATED, use src.c1_user_models instead."""

# This is a backward compatibility shim
# All user models have been moved to src.c1_user_models

from src.c1_user_models import (
    User,
    Role,
    UserRole,
    Permission,
    RolePermission,
    Team,
    TeamMember,
    AuthToken,
    UserSession,
    AuditLog,
    UserPreferences,
    LoginAttempt,
)

__all__ = [
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
]
