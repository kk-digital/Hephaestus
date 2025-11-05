"""Pytest configuration and global fixtures for Hephaestus tests.

This file provides test fixtures that are automatically available to all tests.
"""

import pytest
from unittest.mock import patch, MagicMock, Mock
from tests.fixtures.mock_llm_provider import MockLLMProvider


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
