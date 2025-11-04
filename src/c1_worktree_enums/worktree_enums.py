"""Worktree-related enums for Hephaestus."""

from enum import Enum


class MergeStatus(Enum):
    """Enum for worktree merge status."""
    ACTIVE = "active"
    MERGED = "merged"
    ABANDONED = "abandoned"
    CLEANED = "cleaned"


class CommitType(Enum):
    """Enum for commit types."""
    PARENT_CHECKPOINT = "parent_checkpoint"
    VALIDATION_READY = "validation_ready"
    FINAL = "final"
    AUTO_SAVE = "auto_save"
    CONFLICT_RESOLUTION = "conflict_resolution"
