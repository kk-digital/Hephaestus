"""Monitoring Enums for Hephaestus."""

from enum import Enum


class AgentState(Enum):
    """Agent state enumeration."""
    HEALTHY = "healthy"
    STUCK_WAITING = "stuck_waiting"
    STUCK_ERROR = "stuck_error"
    STUCK_CONFUSED = "stuck_confused"
    UNRECOVERABLE = "unrecoverable"


class MonitoringDecision(Enum):
    """Monitoring decision enumeration."""
    CONTINUE = "continue"
    NUDGE = "nudge"
    ANSWER = "answer"
    RESTART = "restart"
    RECREATE = "recreate"
