"""Mock LLM provider for testing without API keys.

This mock provider allows tests to run without real LLM API keys by providing
predictable fake responses for completions, chat, and embeddings.
"""

from typing import Any, Dict, List, Optional
import hashlib


class MockEmbeddings:
    """Mock embeddings API that mimics OpenAI client.embeddings interface."""

    def __init__(self, parent):
        """Initialize mock embeddings API.

        Args:
            parent: Parent MockLLMProvider instance
        """
        self.parent = parent

    def create(
        self,
        input: str,
        model: str = "mock-embedding-model",
        encoding_format: str = "float",
        **kwargs
    ):
        """Create embedding using OpenAI-compatible interface.

        Args:
            input: Text to embed
            model: Model name (ignored in mock)
            encoding_format: Encoding format (ignored in mock)
            **kwargs: Additional parameters (ignored in mock)

        Returns:
            Mock response object with data attribute containing embeddings
        """
        # Use parent's generate_embedding method
        response_dict = self.parent.generate_embedding(input, model, **kwargs)

        # Create mock response object that can be accessed with dot notation
        class MockResponse:
            def __init__(self, response_dict):
                self.data = [type('obj', (object,), {
                    'embedding': response_dict['data'][0]['embedding'],
                    'index': response_dict['data'][0]['index']
                })]
                self.model = response_dict['model']
                self.usage = type('obj', (object,), response_dict['usage'])

        return MockResponse(response_dict)


class MockLLMProvider:
    """Mock LLM provider that returns predictable responses without API calls.

    This mock can be used in tests to avoid:
    - Requiring real API keys
    - Making actual API calls
    - Dealing with rate limits or costs
    - Non-deterministic LLM responses

    Usage:
        provider = MockLLMProvider()
        response = provider.generate_completion("Test prompt")
        assert "Mock response" in response["choices"][0]["text"]
    """

    def __init__(self, provider_name: str = "mock"):
        """Initialize mock LLM provider.

        Args:
            provider_name: Name to identify this mock provider
        """
        self.provider_name = provider_name
        self.call_count = 0
        self.last_request = None
        self.responses = []  # History of all responses
        self.embeddings = MockEmbeddings(self)  # OpenAI-compatible embeddings API

    def generate_completion(
        self,
        prompt: str,
        model: str = "mock-model",
        temperature: float = 0.7,
        max_tokens: int = 100,
        **kwargs
    ) -> Dict[str, Any]:
        """Generate mock text completion.

        Args:
            prompt: Input prompt text
            model: Model name (ignored in mock)
            temperature: Temperature parameter (ignored in mock)
            max_tokens: Max tokens to generate (ignored in mock)
            **kwargs: Additional parameters (ignored in mock)

        Returns:
            Dict with OpenAI-compatible completion response format
        """
        self.call_count += 1
        self.last_request = {
            "type": "completion",
            "prompt": prompt,
            "model": model,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        response = {
            "id": f"mock-completion-{self.call_count}",
            "object": "text_completion",
            "created": 1234567890,
            "model": model,
            "choices": [{
                "text": f"Mock response to: {prompt[:50]}...",
                "index": 0,
                "logprobs": None,
                "finish_reason": "stop",
            }],
            "usage": {
                "prompt_tokens": len(prompt.split()),
                "completion_tokens": 10,
                "total_tokens": len(prompt.split()) + 10,
            },
        }

        self.responses.append(response)
        return response

    def generate_chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str = "mock-model",
        temperature: float = 0.7,
        max_tokens: int = 100,
        **kwargs
    ) -> Dict[str, Any]:
        """Generate mock chat completion.

        Args:
            messages: List of chat messages with role and content
            model: Model name (ignored in mock)
            temperature: Temperature parameter (ignored in mock)
            max_tokens: Max tokens to generate (ignored in mock)
            **kwargs: Additional parameters (ignored in mock)

        Returns:
            Dict with OpenAI-compatible chat completion response format
        """
        self.call_count += 1
        self.last_request = {
            "type": "chat",
            "messages": messages,
            "model": model,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        last_message = messages[-1]["content"] if messages else ""

        response = {
            "id": f"mock-chat-{self.call_count}",
            "object": "chat.completion",
            "created": 1234567890,
            "model": model,
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": f"Mock response to: {last_message[:50]}...",
                },
                "finish_reason": "stop",
            }],
            "usage": {
                "prompt_tokens": sum(len(m["content"].split()) for m in messages),
                "completion_tokens": 10,
                "total_tokens": sum(len(m["content"].split()) for m in messages) + 10,
            },
        }

        self.responses.append(response)
        return response

    def generate_embedding(
        self,
        text: str,
        model: str = "mock-embedding-model",
        **kwargs
    ) -> Dict[str, Any]:
        """Generate mock embedding vector.

        Creates a deterministic fake embedding based on hash of input text.
        Always returns the same embedding for the same input text.

        Args:
            text: Input text to embed
            model: Model name (ignored in mock)
            **kwargs: Additional parameters (ignored in mock)

        Returns:
            Dict with OpenAI-compatible embedding response format
            Embedding vector has 384 dimensions for compatibility with common models
        """
        self.call_count += 1
        self.last_request = {
            "type": "embedding",
            "text": text,
            "model": model,
        }

        # Create deterministic fake embedding from text hash
        # This ensures same text always gets same embedding
        hash_val = int(hashlib.md5(text.encode()).hexdigest(), 16)

        # Generate 384-dimensional embedding (common size for sentence transformers)
        fake_embedding = []
        for i in range(384):
            # Use hash to generate pseudo-random but deterministic values
            val = ((hash_val >> (i % 128)) + i) % 200 - 100
            fake_embedding.append(val / 100.0)  # Normalize to [-1, 1] range

        response = {
            "object": "list",
            "data": [{
                "object": "embedding",
                "embedding": fake_embedding,
                "index": 0,
            }],
            "model": model,
            "usage": {
                "prompt_tokens": len(text.split()),
                "total_tokens": len(text.split()),
            },
        }

        self.responses.append(response)
        return response

    def reset(self):
        """Reset mock state (call count, last request, response history)."""
        self.call_count = 0
        self.last_request = None
        self.responses = []

    def __repr__(self):
        """String representation of mock provider."""
        return f"MockLLMProvider(provider={self.provider_name}, calls={self.call_count})"
