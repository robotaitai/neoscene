"""Tests for the FastAPI endpoints."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from neoscene.app.api import app
from neoscene.core.scene_schema import EnvironmentSpec, SceneSpec


@pytest.fixture
def client():
    """Create a test client for the API."""
    return TestClient(app)


@pytest.fixture
def mock_scene_spec():
    """Create a mock SceneSpec."""
    return SceneSpec(
        name="test_scene",
        environment=EnvironmentSpec(asset_id="orchard"),
        objects=[],
        cameras=[],
    )


class TestHealthEndpoint:
    """Tests for the /health endpoint."""

    def test_health_returns_200(self, client: TestClient) -> None:
        """Test that health endpoint returns 200."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_returns_status(self, client: TestClient) -> None:
        """Test that health returns status field."""
        response = client.get("/health")
        data = response.json()
        assert data["status"] == "healthy"

    def test_health_returns_llm_info(self, client: TestClient) -> None:
        """Test that health returns LLM configuration info."""
        response = client.get("/health")
        data = response.json()
        assert "llm_configured" in data
        assert "llm_available" in data

    def test_health_returns_assets_count(self, client: TestClient) -> None:
        """Test that health returns assets count."""
        response = client.get("/health")
        data = response.json()
        assert "assets_loaded" in data
        assert data["assets_loaded"] > 0


class TestRootEndpoint:
    """Tests for the / endpoint."""

    def test_root_returns_200(self, client: TestClient) -> None:
        """Test that root endpoint returns 200."""
        response = client.get("/")
        assert response.status_code == 200

    def test_root_returns_html(self, client: TestClient) -> None:
        """Test that root returns HTML content."""
        response = client.get("/")
        assert "text/html" in response.headers["content-type"]


class TestApiInfoEndpoint:
    """Tests for the /api endpoint."""

    def test_api_returns_200(self, client: TestClient) -> None:
        """Test that /api endpoint returns 200."""
        response = client.get("/api")
        assert response.status_code == 200

    def test_api_returns_info(self, client: TestClient) -> None:
        """Test that /api returns API info."""
        response = client.get("/api")
        data = response.json()
        assert "name" in data
        assert "version" in data
        assert "docs" in data


class TestAssetsEndpoints:
    """Tests for the /assets endpoints."""

    def test_list_assets_returns_200(self, client: TestClient) -> None:
        """Test that listing assets returns 200."""
        response = client.get("/assets")
        assert response.status_code == 200

    def test_list_assets_returns_list(self, client: TestClient) -> None:
        """Test that assets are returned as a list."""
        response = client.get("/assets")
        data = response.json()

        assert "assets" in data
        assert "total" in data
        assert isinstance(data["assets"], list)

    def test_list_assets_by_category(self, client: TestClient) -> None:
        """Test filtering assets by category."""
        response = client.get("/assets?category=environment")
        data = response.json()

        assert data["total"] > 0
        for asset in data["assets"]:
            assert asset["category"] == "environment"

    def test_search_assets_returns_200(self, client: TestClient) -> None:
        """Test that searching assets returns 200."""
        response = client.post(
            "/assets/search",
            json={"query": "tractor", "limit": 5},
        )
        assert response.status_code == 200

    def test_search_assets_returns_results(self, client: TestClient) -> None:
        """Test that search returns relevant results."""
        response = client.post(
            "/assets/search",
            json={"query": "tractor"},
        )
        data = response.json()

        assert "assets" in data
        assert "total" in data


class TestGenerateSceneEndpoint:
    """Tests for the /generate_scene endpoint."""

    @patch("neoscene.app.api.agent")
    def test_generate_scene_returns_200(
        self, mock_agent: MagicMock, client: TestClient, mock_scene_spec: SceneSpec
    ) -> None:
        """Test that scene generation returns 200."""
        mock_agent.generate_and_repair.return_value = mock_scene_spec

        response = client.post(
            "/generate_scene",
            json={"prompt": "An orchard with a tractor"},
        )
        assert response.status_code == 200

    @patch("neoscene.app.api.agent")
    def test_generate_scene_returns_scene_spec(
        self, mock_agent: MagicMock, client: TestClient, mock_scene_spec: SceneSpec
    ) -> None:
        """Test that response contains scene_spec."""
        mock_agent.generate_and_repair.return_value = mock_scene_spec

        response = client.post(
            "/generate_scene",
            json={"prompt": "An orchard with a tractor"},
        )
        data = response.json()

        assert "scene_spec" in data
        assert data["scene_spec"]["name"] == "test_scene"

    @patch("neoscene.app.api.agent")
    def test_generate_scene_returns_mjcf_by_default(
        self, mock_agent: MagicMock, client: TestClient, mock_scene_spec: SceneSpec
    ) -> None:
        """Test that MJCF is included by default."""
        mock_agent.generate_and_repair.return_value = mock_scene_spec

        response = client.post(
            "/generate_scene",
            json={"prompt": "An orchard with a tractor"},
        )
        data = response.json()

        assert "mjcf_xml" in data
        assert data["mjcf_xml"] is not None

    @patch("neoscene.app.api.agent")
    def test_generate_scene_without_mjcf(
        self, mock_agent: MagicMock, client: TestClient, mock_scene_spec: SceneSpec
    ) -> None:
        """Test that MJCF can be excluded."""
        mock_agent.generate_and_repair.return_value = mock_scene_spec

        response = client.post(
            "/generate_scene",
            json={"prompt": "An orchard", "include_mjcf": False},
        )
        data = response.json()

        assert data["mjcf_xml"] is None

    def test_generate_scene_short_prompt_error(self, client: TestClient) -> None:
        """Test that short prompts are rejected."""
        response = client.post(
            "/generate_scene",
            json={"prompt": "ab"},  # Too short
        )
        assert response.status_code == 422
