"""Llm Enums for Hephaestus."""

from enum import Enum


class ComponentType(Enum):
    """Component types for model routing."""
    TASK_ENRICHMENT = "task_enrichment"
    AGENT_MONITORING = "agent_monitoring"
    GUARDIAN_ANALYSIS = "guardian_analysis"
    CONDUCTOR_ANALYSIS = "conductor_analysis"
    AGENT_PROMPTS = "agent_prompts"
