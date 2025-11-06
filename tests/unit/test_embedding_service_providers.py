"""Unit tests for EmbeddingService with multiple providers (OpenAI and LM Studio)."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from src.c2_embedding_service.embedding_service import EmbeddingService


class TestEmbeddingServiceProviders:
    """Test EmbeddingService with different providers."""

    @patch('src.c2_embedding_service.embedding_service.get_config')
    @patch('src.c2_embedding_service.embedding_service.openai.OpenAI')
    def test_init_with_openai_default(self, mock_openai_class, mock_get_config):
        """Test initialization with default OpenAI settings (no base_url)."""
        # Setup mock config
        mock_config = Mock()
        mock_config.task_embedding_model = "text-embedding-3-large"
        mock_get_config.return_value = mock_config

        # Create service without base_url (OpenAI mode)
        service = EmbeddingService(openai_api_key="test-key")

        # Verify OpenAI client created without base_url
        mock_openai_class.assert_called_once_with(api_key="test-key")

        # Verify model from config
        assert service.model == "text-embedding-3-large"
        assert service.base_url is None

    @patch('src.c2_embedding_service.embedding_service.get_config')
    @patch('src.c2_embedding_service.embedding_service.openai.OpenAI')
    def test_init_with_lmstudio(self, mock_openai_class, mock_get_config):
        """Test initialization with LM Studio base_url."""
        # Setup mock config
        mock_config = Mock()
        mock_config.task_embedding_model = "text-embedding-3-large"
        mock_get_config.return_value = mock_config

        # Create service with LM Studio base_url
        lmstudio_url = "http://localhost:1234/v1"
        service = EmbeddingService(
            openai_api_key="lm-studio",
            base_url=lmstudio_url
        )

        # Verify OpenAI client created with base_url
        mock_openai_class.assert_called_once_with(
            api_key="lm-studio",
            base_url=lmstudio_url
        )

        # Verify base_url stored
        assert service.base_url == lmstudio_url
        assert service.model == "text-embedding-3-large"

    @patch('src.c2_embedding_service.embedding_service.get_config')
    @patch('src.c2_embedding_service.embedding_service.openai.OpenAI')
    def test_init_with_model_override(self, mock_openai_class, mock_get_config):
        """Test initialization with model override."""
        # Setup mock config
        mock_config = Mock()
        mock_config.task_embedding_model = "text-embedding-3-large"
        mock_get_config.return_value = mock_config

        # Create service with model override
        custom_model = "nomic-embed-text-v1.5"
        service = EmbeddingService(
            openai_api_key="lm-studio",
            base_url="http://localhost:1234/v1",
            model=custom_model
        )

        # Verify custom model used instead of config
        assert service.model == custom_model

    @patch('src.c2_embedding_service.embedding_service.get_config')
    @patch('src.c2_embedding_service.embedding_service.openai.OpenAI')
    @pytest.mark.asyncio
    async def test_generate_embedding_openai(self, mock_openai_class, mock_get_config):
        """Test embedding generation with OpenAI."""
        # Setup mock config
        mock_config = Mock()
        mock_config.task_embedding_model = "text-embedding-3-large"
        mock_get_config.return_value = mock_config

        # Setup mock OpenAI client
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        # Setup mock embeddings response
        mock_embedding_data = Mock()
        mock_embedding_data.embedding = [0.1, 0.2, 0.3] * 1024  # 3072 dims
        mock_response = Mock()
        mock_response.data = [mock_embedding_data]
        mock_client.embeddings.create.return_value = mock_response

        # Create service and generate embedding
        service = EmbeddingService(openai_api_key="test-key")
        embedding = await service.generate_embedding("test text")

        # Verify embedding generated
        assert len(embedding) == 3072
        assert embedding[0] == 0.1
        mock_client.embeddings.create.assert_called_once()

        # Verify correct parameters passed
        call_kwargs = mock_client.embeddings.create.call_args[1]
        assert call_kwargs['model'] == "text-embedding-3-large"
        assert call_kwargs['input'] == "test text"
        assert call_kwargs['encoding_format'] == "float"

    @patch('src.c2_embedding_service.embedding_service.get_config')
    @patch('src.c2_embedding_service.embedding_service.openai.OpenAI')
    @pytest.mark.asyncio
    async def test_generate_embedding_lmstudio(self, mock_openai_class, mock_get_config):
        """Test embedding generation with LM Studio."""
        # Setup mock config
        mock_config = Mock()
        mock_config.task_embedding_model = "text-embedding-3-large"
        mock_get_config.return_value = mock_config

        # Setup mock OpenAI client
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        # Setup mock embeddings response (384 dims for nomic-embed)
        mock_embedding_data = Mock()
        mock_embedding_data.embedding = [0.5] * 384
        mock_response = Mock()
        mock_response.data = [mock_embedding_data]
        mock_client.embeddings.create.return_value = mock_response

        # Create service with LM Studio settings
        service = EmbeddingService(
            openai_api_key="lm-studio",
            base_url="http://localhost:1234/v1",
            model="nomic-embed-text"
        )

        embedding = await service.generate_embedding("test text")

        # Verify embedding generated with correct dimensions
        assert len(embedding) == 384
        assert embedding[0] == 0.5

        # Verify OpenAI client was called with LM Studio model
        call_kwargs = mock_client.embeddings.create.call_args[1]
        assert call_kwargs['model'] == "nomic-embed-text"

    @patch('src.c2_embedding_service.embedding_service.get_config')
    @patch('src.c2_embedding_service.embedding_service.openai.OpenAI')
    def test_calculate_similarity_same_for_both_providers(
        self, mock_openai_class, mock_get_config
    ):
        """Test that similarity calculation works identically for both providers."""
        # Setup mock config
        mock_config = Mock()
        mock_config.task_embedding_model = "text-embedding-3-large"
        mock_get_config.return_value = mock_config

        # Create two services (OpenAI and LM Studio)
        service_openai = EmbeddingService(openai_api_key="test-key")
        service_lmstudio = EmbeddingService(
            openai_api_key="lm-studio",
            base_url="http://localhost:1234/v1"
        )

        # Test vectors
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [0.0, 1.0, 0.0]
        vec3 = [1.0, 0.0, 0.0]  # Same as vec1

        # Calculate similarities
        sim_openai_different = service_openai.calculate_cosine_similarity(vec1, vec2)
        sim_lmstudio_different = service_lmstudio.calculate_cosine_similarity(vec1, vec2)

        sim_openai_same = service_openai.calculate_cosine_similarity(vec1, vec3)
        sim_lmstudio_same = service_lmstudio.calculate_cosine_similarity(vec1, vec3)

        # Verify both providers give same results
        assert sim_openai_different == sim_lmstudio_different == 0.0
        assert sim_openai_same == sim_lmstudio_same == 1.0

    @patch('src.c2_embedding_service.embedding_service.get_config')
    @patch('src.c2_embedding_service.embedding_service.openai.OpenAI')
    def test_batch_similarities_both_providers(self, mock_openai_class, mock_get_config):
        """Test batch similarity calculation works for both providers."""
        # Setup mock config
        mock_config = Mock()
        mock_config.task_embedding_model = "text-embedding-3-large"
        mock_get_config.return_value = mock_config

        # Create services
        service_openai = EmbeddingService(openai_api_key="test-key")
        service_lmstudio = EmbeddingService(
            openai_api_key="lm-studio",
            base_url="http://localhost:1234/v1"
        )

        # Test data
        query_embedding = [1.0, 0.0, 0.0]
        embeddings = [
            [1.0, 0.0, 0.0],  # Same as query
            [0.0, 1.0, 0.0],  # Orthogonal
            [0.5, 0.5, 0.0]   # Partially similar
        ]

        # Calculate batch similarities
        sim_openai = service_openai.calculate_batch_similarities(query_embedding, embeddings)
        sim_lmstudio = service_lmstudio.calculate_batch_similarities(query_embedding, embeddings)

        # Verify both providers give same results
        assert len(sim_openai) == len(sim_lmstudio) == 3
        for i in range(3):
            assert abs(sim_openai[i] - sim_lmstudio[i]) < 0.0001

    @patch('src.c2_embedding_service.embedding_service.get_config')
    @patch('src.c2_embedding_service.embedding_service.openai.OpenAI')
    @pytest.mark.asyncio
    async def test_text_truncation_both_providers(self, mock_openai_class, mock_get_config):
        """Test text truncation works for both providers."""
        # Setup mock config
        mock_config = Mock()
        mock_config.task_embedding_model = "text-embedding-3-large"
        mock_get_config.return_value = mock_config

        # Setup mock client
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        mock_embedding_data = Mock()
        mock_embedding_data.embedding = [0.1] * 100
        mock_response = Mock()
        mock_response.data = [mock_embedding_data]
        mock_client.embeddings.create.return_value = mock_response

        # Create service
        service = EmbeddingService(
            openai_api_key="lm-studio",
            base_url="http://localhost:1234/v1"
        )

        # Generate very long text
        long_text = "x" * 40000  # Exceeds 30000 char limit

        await service.generate_embedding(long_text)

        # Verify text was truncated
        call_kwargs = mock_client.embeddings.create.call_args[1]
        assert len(call_kwargs['input']) == 30000

    @patch('src.c2_embedding_service.embedding_service.get_config')
    @patch('src.c2_embedding_service.embedding_service.openai.OpenAI')
    @pytest.mark.asyncio
    async def test_generate_ticket_embedding_lmstudio(
        self, mock_openai_class, mock_get_config
    ):
        """Test ticket embedding generation with LM Studio."""
        # Setup mock config
        mock_config = Mock()
        mock_config.task_embedding_model = "text-embedding-3-large"
        mock_get_config.return_value = mock_config

        # Setup mock client
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        mock_embedding_data = Mock()
        mock_embedding_data.embedding = [0.1] * 384
        mock_response = Mock()
        mock_response.data = [mock_embedding_data]
        mock_client.embeddings.create.return_value = mock_response

        # Create LM Studio service
        service = EmbeddingService(
            openai_api_key="lm-studio",
            base_url="http://localhost:1234/v1",
            model="nomic-embed-text"
        )

        # Generate ticket embedding
        embedding = await service.generate_ticket_embedding(
            title="Test Ticket",
            description="This is a test description",
            tags=["bug", "urgent"]
        )

        # Verify embedding generated
        assert len(embedding) == 384
        mock_client.embeddings.create.assert_called_once()

        # Verify weighted text includes title twice
        call_kwargs = mock_client.embeddings.create.call_args[1]
        weighted_text = call_kwargs['input']
        assert weighted_text.count("Test Ticket") == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
