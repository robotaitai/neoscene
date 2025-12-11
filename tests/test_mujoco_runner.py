"""Tests for MuJoCo runner and CLI."""

import subprocess
import sys
import tempfile
from pathlib import Path

import mujoco
import pytest

from neoscene.core.asset_catalog import AssetCatalog
from neoscene.core.scene_schema import SceneSpec, example_scene_spec
from neoscene.exporters.mjcf_exporter import scene_to_mjcf

# Path to assets directory
ASSETS_DIR = Path(__file__).parent.parent / "neoscene" / "assets"
EXAMPLES_DIR = Path(__file__).parent.parent / "examples"


@pytest.fixture
def catalog() -> AssetCatalog:
    """Create an AssetCatalog instance for testing."""
    return AssetCatalog(ASSETS_DIR)


class TestMuJoCoValidation:
    """Tests that verify MuJoCo can load generated MJCF."""

    def test_example_scene_loads_in_mujoco(self, catalog: AssetCatalog) -> None:
        """Test that example_scene_spec generates valid MuJoCo XML."""
        spec = example_scene_spec()
        xml = scene_to_mjcf(spec, catalog)

        # Write to temp file (needed for includes)
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".xml", delete=False
        ) as f:
            f.write(xml)
            temp_path = Path(f.name)

        try:
            # This will raise if the XML is invalid
            model = mujoco.MjModel.from_xml_path(str(temp_path))
            data = mujoco.MjData(model)

            # Basic sanity checks
            assert model.nq >= 0  # Number of generalized coordinates
            assert model.nv >= 0  # Number of degrees of freedom
            assert model.nbody >= 1  # At least worldbody
        finally:
            temp_path.unlink()

    def test_minimal_scene_loads_in_mujoco(self, catalog: AssetCatalog) -> None:
        """Test that a minimal scene loads correctly."""
        from neoscene.core.scene_schema import EnvironmentSpec

        spec = SceneSpec(
            name="minimal_test",
            environment=EnvironmentSpec(asset_id="orchard"),
        )
        xml = scene_to_mjcf(spec, catalog)

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".xml", delete=False
        ) as f:
            f.write(xml)
            temp_path = Path(f.name)

        try:
            model = mujoco.MjModel.from_xml_path(str(temp_path))
            assert model is not None
        finally:
            temp_path.unlink()

    def test_orchard_example_json_loads(self, catalog: AssetCatalog) -> None:
        """Test that the orchard_scene.json example loads correctly."""
        json_path = EXAMPLES_DIR / "orchard_scene.json"

        if not json_path.exists():
            pytest.skip("Example file not found")

        json_content = json_path.read_text()
        spec = SceneSpec.model_validate_json(json_content)
        xml = scene_to_mjcf(spec, catalog)

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".xml", delete=False
        ) as f:
            f.write(xml)
            temp_path = Path(f.name)

        try:
            model = mujoco.MjModel.from_xml_path(str(temp_path))
            assert model is not None
            # Should have multiple bodies (env + tractor + 3 crates)
            assert model.nbody >= 5
        finally:
            temp_path.unlink()


class TestCLI:
    """Tests for the CLI interface."""

    def test_cli_help(self) -> None:
        """Test that --help works."""
        result = subprocess.run(
            [sys.executable, "-m", "neoscene.app.main", "--help"],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent.parent),
        )
        assert result.returncode == 0
        assert "scene-json" in result.stdout
        assert "assets-path" in result.stdout

    def test_cli_missing_scene_file(self) -> None:
        """Test error handling for missing scene file."""
        result = subprocess.run(
            [
                sys.executable, "-m", "neoscene.app.main",
                "--scene-json", "/nonexistent/path.json",
                "--no-viewer",
            ],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent.parent),
        )
        assert result.returncode != 0
        assert "not found" in result.stderr.lower() or "error" in result.stderr.lower()

    def test_cli_invalid_json(self) -> None:
        """Test error handling for invalid JSON."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            f.write("{ invalid json }")
            temp_path = Path(f.name)

        try:
            result = subprocess.run(
                [
                    sys.executable, "-m", "neoscene.app.main",
                    "--scene-json", str(temp_path),
                    "--no-viewer",
                ],
                capture_output=True,
                text=True,
                cwd=str(Path(__file__).parent.parent),
            )
            assert result.returncode != 0
            assert "error" in result.stderr.lower()
        finally:
            temp_path.unlink()

    def test_cli_generates_xml(self) -> None:
        """Test that CLI can generate XML output."""
        scene_json = EXAMPLES_DIR / "orchard_scene.json"

        if not scene_json.exists():
            pytest.skip("Example file not found")

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "output.xml"

            result = subprocess.run(
                [
                    sys.executable, "-m", "neoscene.app.main",
                    "--scene-json", str(scene_json),
                    "--output", str(output_path),
                    "--no-viewer",
                ],
                capture_output=True,
                text=True,
                cwd=str(Path(__file__).parent.parent),
            )

            assert result.returncode == 0
            assert output_path.exists()

            # Verify it's valid XML
            content = output_path.read_text()
            assert "<mujoco" in content

    def test_cli_no_args_shows_usage(self) -> None:
        """Test that running without args shows usage info."""
        result = subprocess.run(
            [sys.executable, "-m", "neoscene.app.main"],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent.parent),
        )
        # Should exit cleanly and show usage
        assert result.returncode == 0
        assert "usage" in result.stdout.lower() or "scene-json" in result.stdout.lower()

