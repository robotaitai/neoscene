"""Tests for the /chat API endpoint."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from neoscene.core.scene_schema import EnvironmentSpec, SceneSpec


@pytest.fixture
def mock_scene_spec():
    """Create a mock SceneSpec."""
    return SceneSpec(
        name="test_scene",
        environment=EnvironmentSpec(asset_id="orchard"),
        objects=[],
        cameras=[],
    )


@pytest.fixture
def client(mock_scene_spec):
    """Create a test client with mocked dependencies."""
    with patch("neoscene.app.api.agent") as mock_agent, \
         patch("neoscene.app.api.session_manager") as mock_session_mgr:
        
        # Setup mock agent
        mock_agent.generate_and_repair.return_value = mock_scene_spec
        
        # Setup mock session manager
        mock_session = MagicMock()
        mock_session.session_id = "test-session-123"
        mock_session.last_scene = mock_scene_spec
        
        mock_session_mgr.get_or_create_session.return_value = mock_session
        mock_session_mgr.describe_scene.return_value = {
            "has_scene": True,
            "scene_name": "test_scene",
            "environment_asset_id": "orchard",
            "object_count": 0,
            "camera_count": 0,
        }
        mock_session_mgr.catalog = MagicMock()
        mock_session_mgr.catalog.__len__ = MagicMock(return_value=8)
        
        from neoscene.app.api import app
        yield TestClient(app)


class TestChatEndpoint:
    """Tests for POST /chat endpoint."""

    def test_chat_empty_message_returns_400(self, client: TestClient) -> None:
        """Test that empty message returns 400."""
        response = client.post("/chat", json={"message": ""})
        assert response.status_code == 400

    def test_chat_whitespace_message_returns_400(self, client: TestClient) -> None:
        """Test that whitespace-only message returns 400."""
        response = client.post("/chat", json={"message": "   "})
        assert response.status_code == 400

    def test_chat_returns_200_with_valid_message(self, client: TestClient) -> None:
        """Test that valid message returns 200."""
        response = client.post("/chat", json={"message": "simple scene"})
        assert response.status_code == 200

    def test_chat_returns_session_id(self, client: TestClient) -> None:
        """Test that response contains session_id."""
        response = client.post("/chat", json={"message": "simple scene"})
        data = response.json()

        assert "session_id" in data
        assert data["session_id"] is not None
        assert len(data["session_id"]) > 0

    def test_chat_returns_scene_summary(self, client: TestClient) -> None:
        """Test that response contains scene_summary."""
        response = client.post("/chat", json={"message": "simple scene"})
        data = response.json()

        assert "scene_summary" in data
        assert data["scene_summary"]["has_scene"] is True

    def test_chat_response_structure(self, client: TestClient) -> None:
        """Test that response has correct structure."""
        response = client.post("/chat", json={"message": "test scene"})
        data = response.json()

        assert "session_id" in data
        assert "user_message" in data
        assert "assistant_message" in data
        assert "scene_spec" in data
        assert "scene_summary" in data

    def test_chat_scene_summary_has_correct_fields(self, client: TestClient) -> None:
        """Test that scene_summary contains expected fields."""
        response = client.post("/chat", json={"message": "test scene"})
        summary = response.json()["scene_summary"]

        assert "has_scene" in summary
        assert "scene_name" in summary
        assert "environment_asset_id" in summary
        assert "object_count" in summary
        assert "camera_count" in summary

    def test_chat_user_message_echoed(self, client: TestClient) -> None:
        """Test that user message is echoed in response."""
        message = "a field with a tractor"
        response = client.post("/chat", json={"message": message})
        data = response.json()

        assert data["user_message"] == message
