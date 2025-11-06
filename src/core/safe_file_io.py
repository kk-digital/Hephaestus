"""Safe file I/O wrapper that enforces path policies.

This module provides safe file I/O operations that automatically validate
all paths through the SafePath wrapper. All file operations in Hephaestus
should use these functions instead of direct file I/O to prevent test
pollution and ensure proper directory organization.
"""

from pathlib import Path
from typing import Union, Any
import json

from src.core.safe_path import SafePath


class SafeFileIO:
    """
    File I/O wrapper that ENFORCES SafePath usage.

    All file operations must go through this class to ensure paths
    are validated. Automatically converts string paths to SafePath
    objects for validation.

    Example:
        # Reading files
        content = SafeFileIO.read_text("data/logs/app.log")

        # Writing files (creates parent directories automatically)
        SafeFileIO.write_text("data/test/output.txt", "test data")

        # JSON operations
        data = SafeFileIO.read_json("data/config.json")
        SafeFileIO.write_json("data/test/results.json", {"status": "ok"})
    """

    @staticmethod
    def read_text(path: Union[SafePath, str]) -> str:
        """
        Read text file with path validation.

        Args:
            path: SafePath or string path to read

        Returns:
            File contents as string

        Raises:
            ValueError: If path validation fails
            FileNotFoundError: If file does not exist
        """
        if isinstance(path, str):
            path = SafePath(path)

        return path.path.read_text()

    @staticmethod
    def write_text(
        path: Union[SafePath, str], content: str, allow_create: bool = True
    ):
        """
        Write text file with path validation.

        Args:
            path: SafePath or string path to write
            content: Text content to write
            allow_create: Create parent directories if they don't exist

        Raises:
            ValueError: If path validation fails
        """
        if isinstance(path, str):
            path = SafePath(path, allow_create=allow_create)

        path.path.write_text(content)

    @staticmethod
    def read_bytes(path: Union[SafePath, str]) -> bytes:
        """
        Read binary file with path validation.

        Args:
            path: SafePath or string path to read

        Returns:
            File contents as bytes

        Raises:
            ValueError: If path validation fails
            FileNotFoundError: If file does not exist
        """
        if isinstance(path, str):
            path = SafePath(path)

        return path.path.read_bytes()

    @staticmethod
    def write_bytes(
        path: Union[SafePath, str], content: bytes, allow_create: bool = True
    ):
        """
        Write binary file with path validation.

        Args:
            path: SafePath or string path to write
            content: Binary content to write
            allow_create: Create parent directories if they don't exist

        Raises:
            ValueError: If path validation fails
        """
        if isinstance(path, str):
            path = SafePath(path, allow_create=allow_create)

        path.path.write_bytes(content)

    @staticmethod
    def read_json(path: Union[SafePath, str]) -> Any:
        """
        Read JSON file with path validation.

        Args:
            path: SafePath or string path to read

        Returns:
            Parsed JSON data (dict, list, or other JSON type)

        Raises:
            ValueError: If path validation fails
            FileNotFoundError: If file does not exist
            json.JSONDecodeError: If JSON is invalid
        """
        if isinstance(path, str):
            path = SafePath(path)

        with open(path.path, "r") as f:
            return json.load(f)

    @staticmethod
    def write_json(
        path: Union[SafePath, str], data: Any, allow_create: bool = True, indent: int = 2
    ):
        """
        Write JSON file with path validation.

        Args:
            path: SafePath or string path to write
            data: Data to serialize as JSON
            allow_create: Create parent directories if they don't exist
            indent: JSON indentation level (default: 2)

        Raises:
            ValueError: If path validation fails
            TypeError: If data is not JSON serializable
        """
        if isinstance(path, str):
            path = SafePath(path, allow_create=allow_create)

        with open(path.path, "w") as f:
            json.dump(data, f, indent=indent)

    @staticmethod
    def exists(path: Union[SafePath, str]) -> bool:
        """
        Check if file exists with path validation.

        Args:
            path: SafePath or string path to check

        Returns:
            True if file exists, False otherwise

        Raises:
            ValueError: If path validation fails
        """
        if isinstance(path, str):
            path = SafePath(path)

        return path.path.exists()

    @staticmethod
    def delete(path: Union[SafePath, str]):
        """
        Delete file with path validation.

        Args:
            path: SafePath or string path to delete

        Raises:
            ValueError: If path validation fails
            FileNotFoundError: If file does not exist
        """
        if isinstance(path, str):
            path = SafePath(path)

        if path.path.exists():
            path.path.unlink()

    @staticmethod
    def mkdir(path: Union[SafePath, str], parents: bool = True, exist_ok: bool = True):
        """
        Create directory with path validation.

        Args:
            path: SafePath or string path to create
            parents: Create parent directories if they don't exist
            exist_ok: Don't raise error if directory already exists

        Raises:
            ValueError: If path validation fails
            FileExistsError: If directory exists and exist_ok=False
        """
        if isinstance(path, str):
            path = SafePath(path, allow_create=parents)

        path.path.mkdir(parents=parents, exist_ok=exist_ok)

    @staticmethod
    def open(path: Union[SafePath, str], mode: str = "r", **kwargs):
        """
        Open file with path validation (returns file handle).

        Args:
            path: SafePath or string path to open
            mode: File open mode ('r', 'w', 'a', 'rb', 'wb', etc.)
            **kwargs: Additional arguments passed to open()

        Returns:
            File handle (use with context manager: with SafeFileIO.open(...) as f:)

        Raises:
            ValueError: If path validation fails
            FileNotFoundError: If file does not exist (read modes)
        """
        allow_create = "w" in mode or "a" in mode
        if isinstance(path, str):
            path = SafePath(path, allow_create=allow_create)

        return open(path.path, mode, **kwargs)
