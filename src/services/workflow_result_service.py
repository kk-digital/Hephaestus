"""Backward compatibility shim for WorkflowResultService.

This module re-exports WorkflowResultService from its new location in the c2 layer.
Old imports will continue to work:
    from src.services.workflow_result_service import WorkflowResultService

New code should import from:
    from src.c2_workflow_result_service import WorkflowResultService
"""

from src.c2_workflow_result_service.result_service import WorkflowResultService

__all__ = ["WorkflowResultService"]
