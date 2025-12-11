"""Tests for error handling and custom exceptions."""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from neoscene.core.asset_catalog import AssetCatalog
from neoscene.core.errors import (
    AssetNotFoundError,
    ConfigurationError,
    LayoutError,
    LLMError,
    MJCFExportError,
    NeosceneError,
    SceneValidationError,
)
from neoscene.core.llm_client import GeminiClient
from neoscene.core.scene_agent import SceneAgent, SceneGenerationError
from neoscene.core.scene_schema import SceneSpec

# Path to assets directory
ASSETS_DIR = Path(__file__).parent.parent / "neoscene" / "assets"


@pytest.fixture
def catalog() -> AssetCatalog:
    """Create an AssetCatalog instance for testing."""
    return AssetCatalog(ASSETS_DIR)


@pytest.fixture
def mock_llm() -> GeminiClient:
    """Create a mocked LLM client."""
    llm = MagicMock(spec=GeminiClient)
    llm.is_configured = True
    llm.is_available = True
    return llm


@pytest.fixture
def agent(catalog: AssetCatalog, mock_llm: GeminiClient) -> SceneAgent:
    """Create a SceneAgent with mocked LLM."""
    return SceneAgent(catalog, mock_llm)


class TestNeosceneError:
    """Tests for the base NeosceneError."""

    def test_basic_error(self) -> None:
        """Test creating a basic error."""
        error = NeosceneError("Something went wrong")
        assert str(error) == "Something went wrong"
        assert error.message == "Something went wrong"

    def test_error_with_details(self) -> None:
        """Test error with details dict."""
        error = NeosceneError("Error", details={"key": "value"})
        assert error.details == {"key": "value"}

    def test_to_dict(self) -> None:
        """Test converting error to dict."""
        error = NeosceneError("Test error", details={"foo": "bar"})
        result = error.to_dict()

        assert result["error"] == "NeosceneError"
        assert result["message"] == "Test error"
        assert result["details"] == {"foo": "bar"}


class TestAssetNotFoundError:
    """Tests for AssetNotFoundError."""

    def test_basic_asset_not_found(self) -> None:
        """Test basic asset not found error."""
        error = AssetNotFoundError("missing_asset")
        assert "missing_asset" in str(error)
        assert error.asset_id == "missing_asset"

    def test_with_suggestions(self) -> None:
        """Test error with suggestions."""
        error = AssetNotFoundError(
            "tractorr",
            suggestions=["tractor_red", "tractor_bluewhite"],
        )
        assert "tractor_red" in str(error)
        assert error.suggestions == ["tractor_red", "tractor_bluewhite"]

    def test_with_category(self) -> None:
        """Test error with category."""
        error = AssetNotFoundError("missing", category="robot")
        assert "robot" in str(error)
        assert error.category == "robot"

    def test_catalog_get_raises_error(self, catalog: AssetCatalog) -> None:
        """Test that catalog.get raises AssetNotFoundError."""
        with pytest.raises(AssetNotFoundError) as exc_info:
            catalog.get("nonexistent_asset_id")

        error = exc_info.value
        assert error.asset_id == "nonexistent_asset_id"

    def test_catalog_get_path_raises_error(self, catalog: AssetCatalog) -> None:
        """Test that catalog.get_path raises AssetNotFoundError."""
        with pytest.raises(AssetNotFoundError):
            catalog.get_path("nonexistent_asset_id")

    def test_catalog_suggests_similar(self, catalog: AssetCatalog) -> None:
        """Test that catalog suggests similar assets."""
        with pytest.raises(AssetNotFoundError) as exc_info:
            catalog.get("tractor")  # Partial match

        error = exc_info.value
        # Should suggest tractor_red or tractor_bluewhite
        assert len(error.suggestions) > 0


class TestSceneValidationError:
    """Tests for SceneValidationError."""

    def test_basic_validation_error(self) -> None:
        """Test basic validation error."""
        error = SceneValidationError("Validation failed")
        assert "Validation failed" in str(error)

    def test_with_validation_errors(self) -> None:
        """Test error with validation error list."""
        error = SceneValidationError(
            "Invalid scene",
            validation_errors=["Missing environment", "Invalid position"],
        )
        assert len(error.validation_errors) == 2
        assert "Missing environment" in error.validation_errors

    def test_with_raw_data(self) -> None:
        """Test error with raw data."""
        raw = '{"invalid": "json"}'
        error = SceneValidationError("Parse error", raw_data=raw)
        assert error.raw_data == raw

    def test_agent_raises_on_invalid_json(
        self, agent: SceneAgent, mock_llm: MagicMock
    ) -> None:
        """Test that agent raises SceneValidationError for invalid JSON."""
        mock_llm.generate.return_value = '{"invalid": json here}'

        with pytest.raises(SceneValidationError) as exc_info:
            agent.generate_scene_spec("A scene")

        assert len(exc_info.value.validation_errors) > 0

    def test_agent_raises_on_invalid_schema(
        self, agent: SceneAgent, mock_llm: MagicMock
    ) -> None:
        """Test that agent raises SceneValidationError for invalid schema."""
        # Missing required 'environment' field
        mock_llm.generate.return_value = '{"name": "test"}'

        with pytest.raises(SceneValidationError) as exc_info:
            agent.generate_scene_spec("A scene")

        # Should mention the missing field
        errors_str = str(exc_info.value.validation_errors)
        assert "environment" in errors_str.lower() or "validation" in str(exc_info.value).lower()

    def test_agent_raises_on_invalid_asset_id(
        self, agent: SceneAgent, mock_llm: MagicMock
    ) -> None:
        """Test that agent raises error for invalid asset_id."""
        mock_llm.generate.return_value = """{
            "name": "test",
            "environment": {"asset_id": "fake_environment"},
            "objects": []
        }"""

        with pytest.raises(SceneValidationError) as exc_info:
            agent.generate_scene_spec("A scene")

        assert "fake_environment" in str(exc_info.value.validation_errors)


class TestLLMError:
    """Tests for LLMError."""

    def test_basic_llm_error(self) -> None:
        """Test basic LLM error."""
        error = LLMError("API call failed")
        assert "API call failed" in str(error)
        assert error.llm_provider == "gemini"

    def test_with_original_error(self) -> None:
        """Test LLM error wrapping original exception."""
        original = ValueError("Rate limit exceeded")
        error = LLMError("LLM failed", original_error=original)
        assert error.original_error == original


class TestLayoutError:
    """Tests for LayoutError."""

    def test_layout_error(self) -> None:
        """Test layout error."""
        error = LayoutError(
            "Cannot place 100 objects in 1m radius",
            layout_type="random",
            count=100,
        )
        assert error.layout_type == "random"
        assert error.count == 100


class TestMJCFExportError:
    """Tests for MJCFExportError."""

    def test_export_error(self) -> None:
        """Test MJCF export error."""
        error = MJCFExportError("XML generation failed", asset_id="broken_asset")
        assert error.asset_id == "broken_asset"


class TestConfigurationError:
    """Tests for ConfigurationError."""

    def test_config_error(self) -> None:
        """Test configuration error."""
        error = ConfigurationError("API key missing", config_key="GEMINI_API_KEY")
        assert error.config_key == "GEMINI_API_KEY"


class TestSceneGenerationError:
    """Tests for SceneGenerationError integration."""

    def test_generation_error_after_retries(
        self, agent: SceneAgent, mock_llm: MagicMock
    ) -> None:
        """Test that generation fails after max retries."""
        # Always return invalid JSON
        mock_llm.generate.return_value = '{"name": "test"}'  # Missing environment

        with pytest.raises(SceneGenerationError) as exc_info:
            agent.generate_and_repair("A scene")

        assert "Failed to generate" in str(exc_info.value)


class TestErrorInAPI:
    """Tests for error handling in the API."""

    def test_api_returns_friendly_error(self) -> None:
        """Test that API returns friendly error responses."""
        from fastapi.testclient import TestClient
        from unittest.mock import patch

        from neoscene.app.api import app

        client = TestClient(app, raise_server_exceptions=False)

        # Mock the agent to raise a SceneGenerationError
        from neoscene.core.scene_agent import SceneGenerationError

        with patch("neoscene.app.api.agent") as mock_agent:
            mock_agent.generate_and_repair.side_effect = SceneGenerationError(
                "Failed to generate scene"
            )

            response = client.post(
                "/generate_scene",
                json={"prompt": "test scene"},
            )

        # Should return 400 for generation errors (NeosceneError)
        assert response.status_code == 400

        data = response.json()
        assert "error" in data
        assert "message" in data

