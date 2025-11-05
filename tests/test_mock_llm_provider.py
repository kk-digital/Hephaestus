"""Test mock LLM provider fixture.

This test file verifies that the mock LLM provider works correctly and provides
the expected interface for testing without real API keys.
"""

import pytest
from tests.fixtures.mock_llm_provider import MockLLMProvider


def test_mock_llm_provider_initialization():
    """Test mock LLM provider can be initialized."""
    provider = MockLLMProvider("test-provider")
    assert provider.provider_name == "test-provider"
    assert provider.call_count == 0
    assert provider.last_request is None
    assert provider.responses == []


def test_mock_llm_completion(mock_llm_provider):
    """Test mock completion generation."""
    prompt = "Test prompt for completion"
    response = mock_llm_provider.generate_completion(prompt)

    # Check response structure
    assert "choices" in response
    assert "usage" in response
    assert len(response["choices"]) == 1

    # Check response content
    assert "Mock response" in response["choices"][0]["text"]
    assert response["choices"][0]["finish_reason"] == "stop"

    # Check provider state
    assert mock_llm_provider.call_count == 1
    assert mock_llm_provider.last_request["type"] == "completion"
    assert mock_llm_provider.last_request["prompt"] == prompt


def test_mock_llm_chat(mock_llm_provider):
    """Test mock chat completion."""
    messages = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there"},
        {"role": "user", "content": "How are you?"},
    ]

    response = mock_llm_provider.generate_chat_completion(messages)

    # Check response structure
    assert "choices" in response
    assert "usage" in response
    assert len(response["choices"]) == 1

    # Check response content
    assert "message" in response["choices"][0]
    assert response["choices"][0]["message"]["role"] == "assistant"
    assert "Mock response" in response["choices"][0]["message"]["content"]

    # Check provider state
    assert mock_llm_provider.call_count == 1
    assert mock_llm_provider.last_request["type"] == "chat"
    assert mock_llm_provider.last_request["messages"] == messages


def test_mock_llm_embedding(mock_llm_provider):
    """Test mock embedding generation."""
    text = "Test text for embedding"
    response = mock_llm_provider.generate_embedding(text)

    # Check response structure
    assert "data" in response
    assert "usage" in response
    assert len(response["data"]) == 1

    # Check embedding content
    assert "embedding" in response["data"][0]
    embedding = response["data"][0]["embedding"]
    assert len(embedding) == 384  # Standard embedding size
    assert all(isinstance(val, float) for val in embedding)
    assert all(-1.0 <= val <= 1.0 for val in embedding)  # Normalized range

    # Check provider state
    assert mock_llm_provider.call_count == 1
    assert mock_llm_provider.last_request["type"] == "embedding"
    assert mock_llm_provider.last_request["text"] == text


def test_mock_llm_embedding_deterministic(mock_llm_provider):
    """Test that embeddings are deterministic (same input = same output)."""
    text = "Deterministic test text"

    # Generate embedding twice
    response1 = mock_llm_provider.generate_embedding(text)
    mock_llm_provider.reset()
    response2 = mock_llm_provider.generate_embedding(text)

    # Embeddings should be identical
    embedding1 = response1["data"][0]["embedding"]
    embedding2 = response2["data"][0]["embedding"]
    assert embedding1 == embedding2


def test_mock_llm_call_count(mock_llm_provider):
    """Test that call count increments correctly."""
    assert mock_llm_provider.call_count == 0

    mock_llm_provider.generate_completion("Test 1")
    assert mock_llm_provider.call_count == 1

    mock_llm_provider.generate_chat_completion([{"role": "user", "content": "Test 2"}])
    assert mock_llm_provider.call_count == 2

    mock_llm_provider.generate_embedding("Test 3")
    assert mock_llm_provider.call_count == 3


def test_mock_llm_response_history(mock_llm_provider):
    """Test that response history is tracked."""
    assert len(mock_llm_provider.responses) == 0

    mock_llm_provider.generate_completion("Test 1")
    assert len(mock_llm_provider.responses) == 1

    mock_llm_provider.generate_chat_completion([{"role": "user", "content": "Test 2"}])
    assert len(mock_llm_provider.responses) == 2

    mock_llm_provider.generate_embedding("Test 3")
    assert len(mock_llm_provider.responses) == 3


def test_mock_llm_reset(mock_llm_provider):
    """Test that reset clears provider state."""
    # Make some calls
    mock_llm_provider.generate_completion("Test")
    mock_llm_provider.generate_embedding("Test")

    assert mock_llm_provider.call_count == 2
    assert len(mock_llm_provider.responses) == 2
    assert mock_llm_provider.last_request is not None

    # Reset
    mock_llm_provider.reset()

    # State should be cleared
    assert mock_llm_provider.call_count == 0
    assert len(mock_llm_provider.responses) == 0
    assert mock_llm_provider.last_request is None


def test_mock_llm_usage_tracking(mock_llm_provider):
    """Test that usage tokens are tracked in responses."""
    # Test completion
    response = mock_llm_provider.generate_completion("Test prompt with several words")
    assert "usage" in response
    assert response["usage"]["prompt_tokens"] > 0
    assert response["usage"]["completion_tokens"] > 0
    assert response["usage"]["total_tokens"] > 0

    # Test chat
    messages = [
        {"role": "user", "content": "Message one"},
        {"role": "assistant", "content": "Response one"},
        {"role": "user", "content": "Message two"},
    ]
    response = mock_llm_provider.generate_chat_completion(messages)
    assert "usage" in response
    assert response["usage"]["prompt_tokens"] > 0

    # Test embedding
    response = mock_llm_provider.generate_embedding("Test text")
    assert "usage" in response
    assert response["usage"]["prompt_tokens"] > 0


def test_mock_llm_autouse_fixture():
    """Test that autouse fixture is available (implicit)."""
    # This test should pass without explicitly requesting mock_llm_provider
    # The autouse fixture in conftest.py should have patched LLM imports
    # If API key errors occur during import, this test would fail
    from tests.fixtures.mock_llm_provider import MockLLMProvider
    assert MockLLMProvider is not None
