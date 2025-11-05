"""Conductor Enums for Hephaestus."""

from enum import Enum


class SystemDecision(Enum):
    """System-level decisions the conductor can make."""
    CONTINUE = "continue"
    TERMINATE_DUPLICATE = "terminate_duplicate"
    COORDINATE_RESOURCES = "coordinate_resources"
    CREATE_MISSING_TASK = "create_missing_task"
    ESCALATE = "escalate"
