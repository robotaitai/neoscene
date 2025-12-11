"""Tests for the SceneAgent."""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from neoscene.core.asset_catalog import AssetCatalog
from neoscene.core.llm_client import GeminiClient
from neoscene.core.errors import SceneValidationError
from neoscene.core.scene_agent import (
    SceneAgent,
    SceneGenerationError,
    _build_asset_catalog_summary,
    _extract_json_from_response,
)
from neoscene.core.scene_schema import SceneSpec

# Path to assets directory
ASSETS_DIR = Path(__file__).parent.parent / "neoscene" / "assets"

# Golden example JSON for testing
GOLDEN_SCENE_JSON = """{
  "name": "test_scene",
  "description": "A test scene with tractor and crates",
  "environment": {
    "asset_id": "orchard",
    "gravity": [0.0, 0.0, -9.81]
  },
  "objects": [
    {
      "asset_id": "tractor_bluewhite",
      "name": "main_tractor",
      "instances": [
        {
          "pose": {
            "position": [5.0, 0.0, 0.0],
            "yaw_deg": 0.0
          }
        }
      ]
    },
    {
      "asset_id": "crate_wooden_small",
      "name": "crates",
      "layout": {
        "type": "grid",
        "origin": [8.0, -1.0, 0.0],
        "rows": 1,
        "cols": 3,
        "spacing": [0.7, 0.7]
      }
    }
  ],
  "cameras": [
    {
      "name": "top_camera",
      "pose": {
        "position": [5.0, 0.0, 10.0],
        "pitch_deg": -90.0
      },
      "fovy": 60.0
    }
  ],
  "physics": {
    "timestep": 0.002,
    "solver": "Newton"
  }
}"""


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


class TestExtractJsonFromResponse:
    """Tests for JSON extraction from LLM responses."""

    def test_extract_from_markdown_code_block(self) -> None:
        """Test extracting JSON from markdown code block."""
        response = '''Here's the scene:

```json
{"name": "test", "environment": {"asset_id": "orchard"}}
```

Done!'''
        result = _extract_json_from_response(response)
        data = json.loads(result)
        assert data["name"] == "test"

    def test_extract_from_plain_code_block(self) -> None:
        """Test extracting JSON from plain code block."""
        response = '''```
{"name": "test"}
```'''
        result = _extract_json_from_response(response)
        data = json.loads(result)
        assert data["name"] == "test"

    def test_extract_raw_json(self) -> None:
        """Test extracting raw JSON without code blocks."""
        response = '{"name": "test", "value": 123}'
        result = _extract_json_from_response(response)
        data = json.loads(result)
        assert data["name"] == "test"

    def test_extract_json_with_surrounding_text(self) -> None:
        """Test extracting JSON surrounded by text."""
        response = 'Here is the result: {"name": "test"} as requested.'
        result = _extract_json_from_response(response)
        data = json.loads(result)
        assert data["name"] == "test"

    def test_no_json_raises_error(self) -> None:
        """Test that missing JSON raises error."""
        response = "I cannot generate a scene for that request."
        with pytest.raises(SceneGenerationError, match="Could not extract JSON"):
            _extract_json_from_response(response)


class TestBuildAssetCatalogSummary:
    """Tests for asset catalog summary building."""

    def test_summary_includes_all_categories(self, catalog: AssetCatalog) -> None:
        """Test that summary includes all asset categories."""
        summary = _build_asset_catalog_summary(catalog)

        assert "Environment" in summary
        assert "Robot" in summary
        assert "Prop" in summary

    def test_summary_includes_asset_ids(self, catalog: AssetCatalog) -> None:
        """Test that summary includes asset IDs."""
        summary = _build_asset_catalog_summary(catalog)

        assert "orchard" in summary
        assert "tractor" in summary
        assert "crate_wooden_small" in summary


class TestSceneAgent:
    """Tests for the SceneAgent class."""

    def test_generate_with_valid_response(
        self, agent: SceneAgent, mock_llm: MagicMock
    ) -> None:
        """Test generation with a valid LLM response."""
        mock_llm.generate.return_value = GOLDEN_SCENE_JSON

        spec = agent.generate_scene_spec("A tractor in an orchard with crates")

        assert isinstance(spec, SceneSpec)
        assert spec.name == "test_scene"
        assert spec.environment.asset_id == "orchard"
        assert len(spec.objects) == 2
        assert len(spec.cameras) == 1

    def test_generate_with_markdown_response(
        self, agent: SceneAgent, mock_llm: MagicMock
    ) -> None:
        """Test generation with markdown-wrapped response."""
        mock_llm.generate.return_value = f"```json\n{GOLDEN_SCENE_JSON}\n```"

        spec = agent.generate_scene_spec("A tractor in an orchard")

        assert isinstance(spec, SceneSpec)
        assert spec.name == "test_scene"

    def test_generate_with_invalid_json_raises(
        self, agent: SceneAgent, mock_llm: MagicMock
    ) -> None:
        """Test that invalid JSON raises SceneValidationError."""
        # JSON that looks extractable but is actually invalid
        mock_llm.generate.return_value = '{"invalid": json here}'

        with pytest.raises(SceneValidationError, match="Invalid JSON"):
            agent.generate_scene_spec("A scene")

    def test_generate_with_invalid_schema_raises(
        self, agent: SceneAgent, mock_llm: MagicMock
    ) -> None:
        """Test that schema validation errors are raised."""
        # Missing required 'environment' field
        mock_llm.generate.return_value = '{"name": "test"}'

        with pytest.raises(SceneValidationError, match="validation failed"):
            agent.generate_scene_spec("A scene")

    def test_generate_with_invalid_asset_id_raises(
        self, agent: SceneAgent, mock_llm: MagicMock
    ) -> None:
        """Test that invalid asset_id raises error."""
        invalid_json = """{
            "name": "test",
            "environment": {"asset_id": "nonexistent_environment"},
            "objects": []
        }"""
        mock_llm.generate.return_value = invalid_json

        with pytest.raises(SceneValidationError, match="Invalid asset references"):
            agent.generate_scene_spec("A scene")

    def test_validation_error_includes_raw_data(
        self, agent: SceneAgent, mock_llm: MagicMock
    ) -> None:
        """Test that validation errors include the raw data."""
        mock_llm.generate.return_value = '{"name": "test"}'

        try:
            agent.generate_scene_spec("A scene")
        except SceneValidationError as e:
            assert e.raw_data is not None
            assert len(e.validation_errors) > 0

    def test_suggest_scene_returns_dict(
        self, agent: SceneAgent, mock_llm: MagicMock
    ) -> None:
        """Test that suggest_scene returns a dictionary."""
        mock_llm.generate.return_value = GOLDEN_SCENE_JSON

        result = agent.suggest_scene("A tractor scene")

        assert isinstance(result, dict)
        assert result["name"] == "test_scene"

    def test_suggest_scene_returns_error_on_failure(
        self, agent: SceneAgent, mock_llm: MagicMock
    ) -> None:
        """Test that suggest_scene returns error dict on failure."""
        mock_llm.generate.return_value = "Not valid JSON at all"

        result = agent.suggest_scene("A scene")

        assert "error" in result


class TestSceneAgentRepair:
    """Tests for the repair functionality."""

    def test_generate_and_repair_succeeds_first_try(
        self, agent: SceneAgent, mock_llm: MagicMock
    ) -> None:
        """Test that repair isn't needed when first attempt succeeds."""
        mock_llm.generate.return_value = GOLDEN_SCENE_JSON

        spec = agent.generate_and_repair("A tractor scene")

        assert isinstance(spec, SceneSpec)
        # Should only call generate once
        assert mock_llm.generate.call_count == 1

    def test_generate_and_repair_repairs_on_failure(
        self, agent: SceneAgent, mock_llm: MagicMock
    ) -> None:
        """Test that repair is attempted on validation failure."""
        # First call returns invalid, second returns valid
        mock_llm.generate.side_effect = [
            '{"name": "test"}',  # Invalid (missing environment)
            GOLDEN_SCENE_JSON,  # Valid
        ]

        spec = agent.generate_and_repair("A tractor scene")

        assert isinstance(spec, SceneSpec)
        assert mock_llm.generate.call_count == 2

    def test_generate_and_repair_gives_up_after_max_attempts(
        self, agent: SceneAgent, mock_llm: MagicMock
    ) -> None:
        """Test that repair gives up after max attempts."""
        # Always return invalid JSON
        mock_llm.generate.return_value = '{"name": "test"}'

        with pytest.raises(SceneGenerationError, match="Failed to generate"):
            agent.generate_and_repair("A scene")

        # Should try initial + max_repair_attempts
        assert mock_llm.generate.call_count == agent.max_repair_attempts + 1


class TestGoldenExample:
    """Tests using the golden example JSON."""

    def test_golden_json_is_valid_scene_spec(self) -> None:
        """Test that the golden JSON is a valid SceneSpec."""
        data = json.loads(GOLDEN_SCENE_JSON)
        spec = SceneSpec.model_validate(data)

        assert spec.name == "test_scene"
        assert spec.environment.asset_id == "orchard"
        assert len(spec.objects) == 2

    def test_golden_json_has_correct_structure(self) -> None:
        """Test the golden JSON structure."""
        data = json.loads(GOLDEN_SCENE_JSON)

        assert "name" in data
        assert "environment" in data
        assert "objects" in data
        assert "cameras" in data

        # Check object structure
        tractor = data["objects"][0]
        assert tractor["asset_id"] == "tractor_bluewhite"
        assert "instances" in tractor

        crates = data["objects"][1]
        assert crates["asset_id"] == "crate_wooden_small"
        assert "layout" in crates
        assert crates["layout"]["type"] == "grid"

