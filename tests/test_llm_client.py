"""Tests for the LLM client module."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from neoscene.core.llm_client import (
    GeminiClient,
    LLMAPIError,
    LLMConfigError,
    get_default_config_path,
    load_llm_config,
)


class TestLoadLLMConfig:
    """Tests for the load_llm_config function."""

    def test_load_default_config(self) -> None:
        """Test loading the default config file."""
        config = load_llm_config()

        # Should have expected keys
        assert "default_model" in config
        assert "temperature" in config
        assert "max_output_tokens" in config

    def test_load_default_config_values(self) -> None:
        """Test that default config has expected values."""
        config = load_llm_config()

        assert config["default_model"] == "gemini-2.0-flash"
        assert config["temperature"] == 0.3
        assert config["max_output_tokens"] == 2048

    def test_load_custom_config(self) -> None:
        """Test loading a custom config file."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            yaml.dump(
                {
                    "default_model": "gemini-1.5-pro",
                    "temperature": 0.7,
                    "max_output_tokens": 4096,
                },
                f,
            )
            temp_path = Path(f.name)

        try:
            config = load_llm_config(temp_path)
            assert config["default_model"] == "gemini-1.5-pro"
            assert config["temperature"] == 0.7
            assert config["max_output_tokens"] == 4096
        finally:
            temp_path.unlink()

    def test_load_nonexistent_config_returns_defaults(self) -> None:
        """Test that nonexistent config file returns defaults."""
        config = load_llm_config(Path("/nonexistent/path/config.yaml"))

        # Should return defaults
        assert config["default_model"] == "gemini-2.0-flash"
        assert config["temperature"] == 0.3

    def test_get_default_config_path(self) -> None:
        """Test that default config path is correct."""
        path = get_default_config_path()
        assert path.name == "llm_config.yaml"
        assert "config" in str(path)


class TestGeminiClient:
    """Tests for the GeminiClient class."""

    def test_init_without_api_key(self) -> None:
        """Test client initialization without API key."""
        # Clear any env vars for this test
        with patch.dict("os.environ", {}, clear=True):
            client = GeminiClient(api_key=None)
            assert not client.is_configured

    def test_init_with_api_key(self) -> None:
        """Test client initialization with API key."""
        client = GeminiClient(api_key="test-api-key")
        assert client.is_configured
        assert client.api_key == "test-api-key"

    def test_init_from_env_gemini_key(self) -> None:
        """Test client reads GEMINI_API_KEY from environment."""
        with patch.dict("os.environ", {"GEMINI_API_KEY": "env-key"}):
            client = GeminiClient()
            assert client.is_configured
            assert client.api_key == "env-key"

    def test_init_from_env_google_key(self) -> None:
        """Test client reads GOOGLE_API_KEY from environment."""
        with patch.dict("os.environ", {"GOOGLE_API_KEY": "google-key"}, clear=True):
            client = GeminiClient()
            assert client.is_configured
            assert client.api_key == "google-key"

    def test_from_default_config(self) -> None:
        """Test creating client from default config."""
        client = GeminiClient.from_default_config()
        assert client.model_name == "gemini-2.0-flash"
        assert client.temperature == 0.3
        assert client.max_output_tokens == 2048

    def test_from_custom_config(self) -> None:
        """Test creating client from custom config."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            yaml.dump(
                {
                    "default_model": "gemini-1.5-pro",
                    "temperature": 0.5,
                    "max_output_tokens": 1024,
                },
                f,
            )
            temp_path = Path(f.name)

        try:
            client = GeminiClient.from_config(temp_path)
            assert client.model_name == "gemini-1.5-pro"
            assert client.temperature == 0.5
            assert client.max_output_tokens == 1024
        finally:
            temp_path.unlink()

    def test_mock_generate_without_api(self) -> None:
        """Test that generate returns mock response without API."""
        with patch.dict("os.environ", {}, clear=True):
            client = GeminiClient()
            response = client.generate("Hello world")

            assert "[MOCK RESPONSE]" in response

    def test_mock_generate_json_response(self) -> None:
        """Test that mock generate returns JSON for scene prompts."""
        with patch.dict("os.environ", {}, clear=True):
            client = GeminiClient()
            response = client.generate("Create a scene with JSON")

            assert "mock_scene" in response
            assert "environment" in response

    def test_generate_json_adds_instruction(self) -> None:
        """Test that generate_json adds JSON instruction."""
        with patch.dict("os.environ", {}, clear=True):
            client = GeminiClient()
            # The mock will still work, but we can verify the method exists
            response = client.generate_json("Create a scene")
            assert response is not None

    def test_repr(self) -> None:
        """Test string representation of client."""
        client = GeminiClient(model_name="gemini-1.5-pro", api_key="test")
        repr_str = repr(client)

        assert "GeminiClient" in repr_str
        assert "gemini-1.5-pro" in repr_str
        assert "configured" in repr_str

    def test_generate_with_custom_params(self) -> None:
        """Test generate with custom temperature and max_tokens."""
        with patch.dict("os.environ", {}, clear=True):
            client = GeminiClient(temperature=0.3, max_output_tokens=1000)

            # Should accept overrides without error
            response = client.generate(
                "Hello",
                temperature=0.8,
                max_output_tokens=500,
            )
            assert response is not None


class TestGeminiClientWithMockedAPI:
    """Tests for GeminiClient with mocked API calls."""

    def test_generate_with_mocked_api(self) -> None:
        """Test generate with mocked Google API."""
        # Create a mock response
        mock_response = MagicMock()
        mock_response.text = "This is a generated response"

        # Create a mock model
        mock_model = MagicMock()
        mock_model.generate_content.return_value = mock_response

        client = GeminiClient(api_key="test-key")
        client._model = mock_model

        response = client.generate("Test prompt")

        assert response == "This is a generated response"
        mock_model.generate_content.assert_called_once()

    def test_generate_api_error_handling(self) -> None:
        """Test that API errors are properly wrapped."""
        mock_model = MagicMock()
        mock_model.generate_content.side_effect = Exception("API Error")

        client = GeminiClient(api_key="test-key")
        client._model = mock_model

        with pytest.raises(LLMAPIError, match="Gemini API call failed"):
            client.generate("Test prompt")

