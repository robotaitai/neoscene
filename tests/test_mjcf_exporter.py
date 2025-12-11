"""Tests for the MJCF exporter."""

import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from neoscene.core.asset_catalog import AssetCatalog
from neoscene.core.scene_schema import (
    CameraSpec,
    EnvironmentSpec,
    GridLayout,
    InstanceSpec,
    ObjectSpec,
    Pose,
    RandomLayout,
    SceneSpec,
    example_scene_spec,
)
from neoscene.exporters.mjcf_exporter import (
    _format_vec,
    _layout_instances,
    _to_euler_deg,
    scene_to_mjcf,
    write_scene_to_file,
)

# Path to assets directory
ASSETS_DIR = Path(__file__).parent.parent / "neoscene" / "assets"


@pytest.fixture
def catalog() -> AssetCatalog:
    """Create an AssetCatalog instance for testing."""
    return AssetCatalog(ASSETS_DIR)


@pytest.fixture
def example_spec() -> SceneSpec:
    """Get the example scene spec."""
    return example_scene_spec()


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_format_vec(self) -> None:
        """Test vector formatting."""
        assert _format_vec([1.0, 2.0, 3.0]) == "1 2 3"
        assert _format_vec([0.0, 0.0, -9.81]) == "0 0 -9.81"

    def test_to_euler_deg(self) -> None:
        """Test Euler angle extraction."""
        pose = Pose(position=[0, 0, 0], yaw_deg=90.0, pitch_deg=45.0, roll_deg=30.0)
        roll, pitch, yaw = _to_euler_deg(pose)
        assert roll == 30.0
        assert pitch == 45.0
        assert yaw == 90.0


class TestLayoutInstances:
    """Tests for layout instance generation."""

    def test_explicit_instances(self, catalog: AssetCatalog) -> None:
        """Test that explicit instances are returned as-is."""
        obj = ObjectSpec(
            asset_id="crate_wooden_small",
            instances=[
                InstanceSpec(pose=Pose(position=[1.0, 0.0, 0.0])),
                InstanceSpec(pose=Pose(position=[2.0, 0.0, 0.0])),
            ],
        )
        instances = _layout_instances(obj, catalog)
        assert len(instances) == 2
        assert instances[0].pose.position == [1.0, 0.0, 0.0]
        assert instances[1].pose.position == [2.0, 0.0, 0.0]

    def test_no_layout_single_instance(self, catalog: AssetCatalog) -> None:
        """Test that no layout creates single instance at origin."""
        obj = ObjectSpec(asset_id="crate_wooden_small")
        instances = _layout_instances(obj, catalog)
        assert len(instances) == 1
        assert instances[0].pose.position == [0.0, 0.0, 0.0]

    def test_grid_layout(self, catalog: AssetCatalog) -> None:
        """Test grid layout generates correct positions."""
        obj = ObjectSpec(
            asset_id="crate_wooden_small",
            layout=GridLayout(
                origin=[0.0, 0.0, 0.0],
                rows=2,
                cols=3,
                spacing=[1.0, 2.0],
            ),
        )
        instances = _layout_instances(obj, catalog)

        # Should generate 2 * 3 = 6 instances
        assert len(instances) == 6

        # Check positions
        positions = [inst.pose.position for inst in instances]

        # Row 0: y=0, cols at x=0, 1, 2
        assert [0.0, 0.0, 0.0] in positions
        assert [1.0, 0.0, 0.0] in positions
        assert [2.0, 0.0, 0.0] in positions

        # Row 1: y=2, cols at x=0, 1, 2
        assert [0.0, 2.0, 0.0] in positions
        assert [1.0, 2.0, 0.0] in positions
        assert [2.0, 2.0, 0.0] in positions

    def test_grid_layout_with_origin(self, catalog: AssetCatalog) -> None:
        """Test grid layout respects origin offset."""
        obj = ObjectSpec(
            asset_id="crate_wooden_small",
            layout=GridLayout(
                origin=[5.0, 5.0, 1.0],
                rows=1,
                cols=2,
                spacing=[1.0, 1.0],
            ),
        )
        instances = _layout_instances(obj, catalog)

        assert len(instances) == 2
        assert instances[0].pose.position == [5.0, 5.0, 1.0]
        assert instances[1].pose.position == [6.0, 5.0, 1.0]

    def test_random_layout(self, catalog: AssetCatalog) -> None:
        """Test random layout generates correct count."""
        obj = ObjectSpec(
            asset_id="crate_wooden_small",
            layout=RandomLayout(
                center=[10.0, 10.0, 0.0],
                radius=5.0,
                count=10,
            ),
        )
        instances = _layout_instances(obj, catalog, seed=42)

        assert len(instances) == 10

        # Check all positions are within radius of center
        for inst in instances:
            dx = inst.pose.position[0] - 10.0
            dy = inst.pose.position[1] - 10.0
            dist = (dx**2 + dy**2) ** 0.5
            assert dist <= 5.0, f"Position {inst.pose.position} outside radius"

    def test_random_layout_reproducible(self, catalog: AssetCatalog) -> None:
        """Test that random layout is reproducible with same seed."""
        obj = ObjectSpec(
            asset_id="crate_wooden_small",
            layout=RandomLayout(center=[0.0, 0.0, 0.0], radius=5.0, count=5),
        )

        instances1 = _layout_instances(obj, catalog, seed=123)
        instances2 = _layout_instances(obj, catalog, seed=123)

        for i1, i2 in zip(instances1, instances2):
            assert i1.pose.position == i2.pose.position


class TestSceneToMJCF:
    """Tests for the main scene_to_mjcf function."""

    def test_returns_valid_xml(
        self, example_spec: SceneSpec, catalog: AssetCatalog
    ) -> None:
        """Test that output is valid XML."""
        xml_str = scene_to_mjcf(example_spec, catalog)

        # Should parse without error
        root = ET.fromstring(xml_str)
        assert root is not None

    def test_root_is_mujoco(
        self, example_spec: SceneSpec, catalog: AssetCatalog
    ) -> None:
        """Test that root tag is 'mujoco'."""
        xml_str = scene_to_mjcf(example_spec, catalog)
        root = ET.fromstring(xml_str)
        assert root.tag == "mujoco"

    def test_has_model_name(
        self, example_spec: SceneSpec, catalog: AssetCatalog
    ) -> None:
        """Test that mujoco element has model name."""
        xml_str = scene_to_mjcf(example_spec, catalog)
        root = ET.fromstring(xml_str)
        assert root.get("model") == "orchard_demo"

    def test_has_option_element(
        self, example_spec: SceneSpec, catalog: AssetCatalog
    ) -> None:
        """Test that physics options are present."""
        xml_str = scene_to_mjcf(example_spec, catalog)
        root = ET.fromstring(xml_str)

        option = root.find("option")
        assert option is not None
        assert option.get("timestep") == "0.002"
        assert option.get("solver") == "Newton"

    def test_has_worldbody(
        self, example_spec: SceneSpec, catalog: AssetCatalog
    ) -> None:
        """Test that worldbody is present."""
        xml_str = scene_to_mjcf(example_spec, catalog)
        root = ET.fromstring(xml_str)

        worldbody = root.find("worldbody")
        assert worldbody is not None

    def test_has_bodies(
        self, example_spec: SceneSpec, catalog: AssetCatalog
    ) -> None:
        """Test that bodies are present in worldbody."""
        xml_str = scene_to_mjcf(example_spec, catalog)
        root = ET.fromstring(xml_str)

        worldbody = root.find("worldbody")
        bodies = worldbody.findall("body")
        assert len(bodies) > 0

    def test_has_geoms(
        self, example_spec: SceneSpec, catalog: AssetCatalog
    ) -> None:
        """Test that geom elements are present (inlined from assets)."""
        xml_str = scene_to_mjcf(example_spec, catalog)
        root = ET.fromstring(xml_str)

        geoms = root.findall(".//geom")
        # Should have ground from env + chassis/wheels from tractor + crates
        assert len(geoms) > 5

    def test_grid_layout_creates_correct_count(
        self, catalog: AssetCatalog
    ) -> None:
        """Test that grid layout creates correct number of bodies."""
        spec = SceneSpec(
            name="grid_test",
            environment=EnvironmentSpec(asset_id="orchard"),
            objects=[
                ObjectSpec(
                    asset_id="crate_wooden_small",
                    name="crate",
                    layout=GridLayout(rows=2, cols=3, spacing=[1.0, 1.0]),
                )
            ],
        )

        xml_str = scene_to_mjcf(spec, catalog)
        root = ET.fromstring(xml_str)

        worldbody = root.find("worldbody")
        # Find bodies with 'crate' in the name
        crate_bodies = [
            b for b in worldbody.findall("body")
            if b.get("name", "").startswith("crate")
        ]

        # Should have 2 * 3 = 6 crate bodies
        assert len(crate_bodies) == 6

    def test_cameras_are_added(
        self, example_spec: SceneSpec, catalog: AssetCatalog
    ) -> None:
        """Test that cameras are added to worldbody."""
        xml_str = scene_to_mjcf(example_spec, catalog)
        root = ET.fromstring(xml_str)

        worldbody = root.find("worldbody")
        cameras = worldbody.findall("camera")

        # example_scene_spec has 2 cameras
        assert len(cameras) == 2

    def test_lights_are_added(
        self, example_spec: SceneSpec, catalog: AssetCatalog
    ) -> None:
        """Test that lights are added to worldbody."""
        xml_str = scene_to_mjcf(example_spec, catalog)
        root = ET.fromstring(xml_str)

        worldbody = root.find("worldbody")
        lights = worldbody.findall("light")

        # example_scene_spec has 1 light
        assert len(lights) >= 1

    def test_minimal_scene(self, catalog: AssetCatalog) -> None:
        """Test exporting a minimal scene."""
        spec = SceneSpec(
            name="minimal",
            environment=EnvironmentSpec(asset_id="orchard"),
        )

        xml_str = scene_to_mjcf(spec, catalog)
        root = ET.fromstring(xml_str)

        assert root.tag == "mujoco"
        assert root.find("worldbody") is not None


class TestWriteSceneToFile:
    """Tests for write_scene_to_file function."""

    def test_writes_file(
        self, example_spec: SceneSpec, catalog: AssetCatalog
    ) -> None:
        """Test that file is written."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "scene.xml"
            write_scene_to_file(example_spec, catalog, path)

            assert path.exists()

            # Verify content is valid XML
            content = path.read_text()
            root = ET.fromstring(content)
            assert root.tag == "mujoco"

    def test_creates_parent_directories(
        self, example_spec: SceneSpec, catalog: AssetCatalog
    ) -> None:
        """Test that parent directories are created."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "subdir" / "nested" / "scene.xml"
            write_scene_to_file(example_spec, catalog, path)

            assert path.exists()

