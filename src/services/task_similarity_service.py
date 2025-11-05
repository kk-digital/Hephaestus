"""Backward compatibility shim for TaskSimilarityService.

This module re-exports TaskSimilarityService from its new location in the c2 layer.
Old imports will continue to work:
    from src.services.task_similarity_service import TaskSimilarityService

New code should import from:
    from src.c2_task_similarity_service import TaskSimilarityService
"""

from src.c2_task_similarity_service.similarity_service import TaskSimilarityService

__all__ = ["TaskSimilarityService"]
