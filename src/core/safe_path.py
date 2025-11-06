"""Safe path wrapper with policy enforcement.

This module provides type-safe path handling that enforces file I/O policies.
All file paths must go through SafePath validation to prevent test pollution
and ensure all file operations occur in designated directories.
"""

from pathlib import Path
from typing import Union
import os


class SafePath:
    """
    Type-safe path wrapper that enforces file I/O policies.

    All paths must go through this wrapper to be validated against
    allowed directory policies. Supports TEST_MODE to restrict test
    file operations to data/test/ only.

    Example:
        # Normal usage
        path = SafePath("data/logs/app.log", allow_create=True)

        # Test mode (automatically enabled by pytest fixture)
        SafePath.enable_test_mode()
        path = SafePath("data/test/output.txt", allow_create=True)
        # SafePath("data/logs/test.log")  # Would raise ValueError in test mode
    """

    # Allowed base directories for file I/O
    ALLOWED_BASES = {
        "data",
        "data/test",
        "data/logs",
        "data/tmp",
        "build",
        "reports",
    }

    # Test mode: restrict to data/test only
    TEST_MODE = False

    def __init__(self, path: Union[str, Path], allow_create: bool = False):
        """
        Create safe path with validation.

        Args:
            path: File or directory path (string or Path object)
            allow_create: Whether to create parent directories if they don't exist

        Raises:
            ValueError: If path is outside allowed directories
            ValueError: If path is outside data/test/ in TEST_MODE
        """
        self._path = Path(path).resolve()
        self._validate()

        if allow_create:
            self._path.parent.mkdir(parents=True, exist_ok=True)

    def _validate(self):
        """
        Validate path is in allowed directory.

        Raises:
            ValueError: If path validation fails
        """
        # Get repo root (parent of parent of parent of this file)
        # safe_path.py is in src/core/, so ../../.. gets to repo root
        repo_root = Path(__file__).parent.parent.parent

        try:
            relative = self._path.relative_to(repo_root)
        except ValueError:
            raise ValueError(
                f"Path outside repository: {self._path}\n"
                f"Repository root: {repo_root}"
            )

        # Check if path starts with allowed base
        allowed = False
        for base in self.ALLOWED_BASES:
            if str(relative).startswith(base):
                allowed = True
                break

        if not allowed:
            raise ValueError(
                f"Path not in allowed directories: {relative}\n"
                f"Allowed directories: {', '.join(sorted(self.ALLOWED_BASES))}\n"
                f"Hint: Use data/, data/test/, data/logs/, data/tmp/, build/, or reports/"
            )

        # In test mode, only allow data/test
        if SafePath.TEST_MODE and not str(relative).startswith("data/test"):
            raise ValueError(
                f"TEST_MODE: Only data/test/ allowed, got: {relative}\n"
                f"Tests must write all output to data/test/ directory"
            )

    @property
    def path(self) -> Path:
        """Get underlying Path object for file operations."""
        return self._path

    def __str__(self) -> str:
        """String representation returns absolute path."""
        return str(self._path)

    def __repr__(self) -> str:
        """Developer representation shows SafePath wrapper."""
        return f"SafePath({self._path})"

    @classmethod
    def enable_test_mode(cls):
        """
        Enable test mode (restrict to data/test only).

        Called automatically by pytest fixture in conftest.py.
        """
        cls.TEST_MODE = True

    @classmethod
    def disable_test_mode(cls):
        """
        Disable test mode (allow all configured directories).

        Called automatically by pytest fixture cleanup.
        """
        cls.TEST_MODE = False
