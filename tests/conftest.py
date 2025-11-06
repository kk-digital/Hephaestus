"""Pytest configuration and global fixtures for Hephaestus tests.

This file provides test fixtures that are automatically available to all tests.
"""

import pytest
import tempfile
import subprocess
import os
import time
from pathlib import Path
from unittest.mock import patch, MagicMock, Mock
from tests.fixtures.mock_llm_provider import MockLLMProvider

# Import libtmux - REQUIRED dependency for tmux fixtures
# Will crash if not available (correct behavior)
import libtmux


@pytest.fixture
def mock_llm_provider():
    """Provide a fresh mock LLM provider for each test.

    This fixture can be explicitly requested in tests that need to assert
    on LLM provider interactions.

    Usage:
        def test_something(mock_llm_provider):
            response = mock_llm_provider.generate_completion("test")
            assert mock_llm_provider.call_count == 1

    Returns:
        MockLLMProvider instance
    """
    provider = MockLLMProvider()
    yield provider
    provider.reset()


@pytest.fixture(autouse=True)
def mock_llm_client_imports(monkeypatch):
    """Automatically mock LLM client initialization in all tests.

    This fixture runs automatically for every test (autouse=True) to prevent
    LLM client import errors when API keys are not configured.

    The fixture patches:
    - LangChain LLM client getter
    - LLMProviderInterface direct instantiation
    - get_cli_agent function (which may initialize LLM clients)

    This allows tests to run without API keys while still testing logic that
    uses LLM providers.

    Returns:
        MockLLMProvider instance that all tests will receive
    """
    mock_provider = MockLLMProvider()

    # Patch LangChain LLM client initialization
    def mock_get_llm_client(*args, **kwargs):
        """Mock function that returns mock provider instead of real client."""
        return mock_provider

    # Patch the LangChain LLM client getter
    try:
        monkeypatch.setattr(
            "src.interfaces.langchain_llm_client.get_llm_client",
            mock_get_llm_client
        )
    except AttributeError:
        # Module may not exist yet or may be structured differently
        pass

    # Patch LLMProviderInterface if used directly
    try:
        mock_interface = Mock()
        mock_interface.return_value = mock_provider
        monkeypatch.setattr(
            "src.interfaces.LLMProviderInterface",
            mock_interface
        )
    except AttributeError:
        pass

    # Patch get_cli_agent to avoid LLM initialization
    try:
        def mock_get_cli_agent(*args, **kwargs):
            """Mock CLI agent that doesn't require LLM."""
            agent = Mock()
            agent.provider = mock_provider
            return agent

        monkeypatch.setattr(
            "src.interfaces.get_cli_agent",
            mock_get_cli_agent
        )
    except AttributeError:
        pass

    # Patch OpenAI client if imported directly
    try:
        mock_openai = Mock()
        mock_openai.return_value = mock_provider
        monkeypatch.setattr("openai.OpenAI", mock_openai)
    except (AttributeError, ImportError):
        pass

    # Patch Anthropic client if imported directly
    try:
        mock_anthropic = Mock()
        mock_anthropic.return_value = mock_provider
        monkeypatch.setattr("anthropic.Anthropic", mock_anthropic)
    except (AttributeError, ImportError):
        pass

    return mock_provider


@pytest.fixture
def mock_database(monkeypatch):
    """Mock database connections for tests that don't need real DB.

    This fixture can be explicitly requested by tests that need to avoid
    database initialization.

    Usage:
        def test_something(mock_database):
            # Test logic here, DB calls will be mocked
            pass
    """
    mock_db = Mock()
    mock_session = Mock()

    try:
        monkeypatch.setattr(
            "src.core.database.get_db",
            lambda: mock_session
        )
    except AttributeError:
        pass

    return mock_db


@pytest.fixture(scope="session")
def test_config():
    """Provide test configuration values.

    This fixture provides configuration that can be used across all tests
    without needing environment variables or .env files.

    Returns:
        Dict of configuration values
    """
    return {
        "database_url": "sqlite:///:memory:",
        "llm_provider": "mock",
        "api_key": "mock-api-key",
        "log_level": "ERROR",  # Reduce log noise during tests
    }


@pytest.fixture
def temp_git_repo():
    """Create a temporary git repository for worktree testing.

    This fixture creates a real git repository in a temporary directory,
    initializes it with a commit, and cleans up after the test.

    Usage:
        def test_worktree_operations(temp_git_repo):
            # temp_git_repo is a Path to initialized git repo
            result = subprocess.run(["git", "status"], cwd=temp_git_repo)
            assert result.returncode == 0

    Returns:
        Path: Path to temporary git repository
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir)

        try:
            # Initialize git repo
            subprocess.run(
                ["git", "init"],
                cwd=repo_path,
                check=True,
                capture_output=True
            )

            # Configure git user (required for commits)
            subprocess.run(
                ["git", "config", "user.email", "test@example.com"],
                cwd=repo_path,
                check=True,
                capture_output=True
            )
            subprocess.run(
                ["git", "config", "user.name", "Test User"],
                cwd=repo_path,
                check=True,
                capture_output=True
            )

            # Create initial file and commit
            readme_file = repo_path / "README.md"
            readme_file.write_text("# Test Repository\n\nThis is a test repository.\n")

            subprocess.run(
                ["git", "add", "."],
                cwd=repo_path,
                check=True,
                capture_output=True
            )
            subprocess.run(
                ["git", "commit", "-m", "Initial commit"],
                cwd=repo_path,
                check=True,
                capture_output=True
            )

            yield repo_path

        except subprocess.CalledProcessError as e:
            pytest.fail(f"Failed to create test git repository: {e}")


@pytest.fixture(scope="session")
def tmux_server():
    """Provide a tmux server for agent communication testing.

    This fixture ensures a tmux server is running for tests that need
    tmux sessions (agent communication, prompt delivery, etc.).

    Returns:
        libtmux.Server: Tmux server instance
    """

    try:
        # Try to get existing server
        server = libtmux.Server()
        server.list_sessions()  # Test if server is responsive
    except Exception:
        # Start tmux server if not running
        try:
            subprocess.run(
                ["tmux", "start-server"],
                check=True,
                capture_output=True
            )
            server = libtmux.Server()
        except (subprocess.CalledProcessError, FileNotFoundError):
            pytest.skip("tmux not available or cannot be started")

    yield server

    # Cleanup: kill any test sessions
    try:
        for session in server.list_sessions():
            if session.name and session.name.startswith("test_"):
                try:
                    session.kill()
                except Exception:
                    pass  # Session may have already been killed
    except Exception:
        pass  # Server may be gone, that's ok


@pytest.fixture
def tmux_session(tmux_server):
    """Provide a clean tmux session for each test.

    This fixture creates a unique tmux session for each test and
    cleans it up automatically after the test completes.

    Usage:
        def test_agent_communication(tmux_session):
            # tmux_session is a libtmux.Session
            pane = tmux_session.attached_pane
            pane.send_keys("echo test")

    Returns:
        libtmux.Session: Unique tmux session for this test
    """
    # Create unique session name
    session_name = f"test_{os.getpid()}_{int(time.time() * 1000000)}"

    # Create session
    try:
        session = tmux_server.new_session(
            session_name=session_name,
            kill_session=True,  # Kill if exists (shouldn't happen)
            attach=False
        )
    except Exception as e:
        pytest.fail(f"Failed to create tmux session: {e}")

    yield session

    # Cleanup: kill session after test
    try:
        session.kill()
    except Exception:
        pass  # Session may have already been killed

# ============================================================================
# FILE I/O SAFETY FIXTURES
# ============================================================================


@pytest.fixture(autouse=True)
def enable_safe_path_test_mode():
    """
    Automatically enable SafePath TEST_MODE for all tests.

    This restricts file I/O to data/test/ only, preventing test pollution.
    Runs automatically for every test (autouse=True).

    The fixture:
    - Enables SafePath.TEST_MODE before each test
    - Disables SafePath.TEST_MODE after each test
    - Ensures tests cannot accidentally write outside data/test/

    Usage:
        Tests automatically get sandboxed file I/O - no action needed.
        All file operations through SafeFileIO will be restricted to data/test/
    """
    from src.core.safe_path import SafePath

    SafePath.enable_test_mode()
    yield
    SafePath.disable_test_mode()


@pytest.fixture
def test_data_dir(tmp_path):
    """
    Provide safe test data directory for test output.

    Returns SafePath pointing to data/test/{unique_test_id}/ directory.
    Parent directories are automatically created.

    Usage:
        def test_something(test_data_dir):
            # test_data_dir is a SafePath to data/test/{unique}/
            from src.core.safe_file_io import SafeFileIO
            SafeFileIO.write_text(test_data_dir.path / "output.txt", "data")

    Args:
        tmp_path: Pytest tmp_path fixture (provides unique path for test)

    Returns:
        SafePath: Validated path to test-specific directory in data/test/
    """
    from src.core.safe_path import SafePath

    # Create unique test directory: data/test/{test_unique_id}/
    test_dir = SafePath(f"data/test/{tmp_path.name}", allow_create=True)
    return test_dir
