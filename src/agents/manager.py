"""Backward compatibility shim for AgentManager."""
from src.c2_agent_service.agent_manager import AgentManager
# Import libtmux for test patching compatibility
import libtmux  # noqa: F401

__all__ = ["AgentManager", "libtmux"]
