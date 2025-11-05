"""Backward compatibility shim for QueueService.

This module re-exports QueueService from its new location in the c2 layer.
Old imports will continue to work:
    from src.services.queue_service import QueueService

New code should import from:
    from src.c2_queue_service import QueueService
"""

from src.c2_queue_service.queue_service import QueueService

__all__ = ["QueueService"]
