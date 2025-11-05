"""Backward compatibility shim for EmbeddingService.

This module re-exports EmbeddingService from its new location in the c2 layer.
Old imports will continue to work:
    from src.services.embedding_service import EmbeddingService

New code should import from:
    from src.c2_embedding_service import EmbeddingService
"""

from src.c2_embedding_service.embedding_service import EmbeddingService

__all__ = ["EmbeddingService"]
