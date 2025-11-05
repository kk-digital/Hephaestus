"""Validation Enums for Hephaestus."""

from enum import Enum


class ValidationCheckType(Enum):
    """Types of validation checks."""
    FILE_EXISTS = "file_exists"
    FILE_CONTAINS = "file_contains"
    COMMAND_SUCCESS = "command_success"
    MANUAL_VERIFICATION = "manual_verification"
    CODE_REVIEW = "code_review"
    TEST_PASS = "test_pass"
    PERFORMANCE_METRIC = "performance_metric"
