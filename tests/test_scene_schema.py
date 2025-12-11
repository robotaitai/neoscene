"""Tests for the SceneSpec schema."""

import json

import pytest
from pydantic import ValidationError

from neoscene.core.scene_schema import (
    CameraSpec,
    EnvironmentSpec,
    GridLayout,
    InstanceSpec,
    LightSpec,
    ObjectSpec,
    PhysicsSpec,
    Pose,
    RandomLayout,
    SceneSpec,
    example_scene_spec,
)


class TestPose:
    """Tests for the Pose model."""

    def test_valid_pose(self) -> None:
        """Test creating a valid pose."""
        pose = Pose(position=[1.0, 2.0, 3.0], yaw_deg=45.0)
        assert pose.position == [1.0, 2.0, 3.0]
        assert pose.yaw_deg == 45.0
        assert pose.pitch_deg == 0.0
        assert pose.roll_deg == 0.0

    def test_pose_requires_3d_position(self) -> None:
        """Test that position must have exactly 3 elements."""
        with pytest.raises(ValidationError):
            Pose(position=[1.0, 2.0])  # Only 2 elements

        with pytest.raises(ValidationError):
            Pose(position=[1.0, 2.0, 3.0, 4.0])  # 4 elements


class TestLayouts:
    """Tests for layout models."""

    def test_grid_layout(self) -> None:
        """Test creating a valid grid layout."""
        layout = GridLayout(rows=3, cols=4, spacing=[1.0, 1.5])
        assert layout.type == "grid"
        assert layout.rows == 3
        assert layout.cols == 4
        assert layout.spacing == [1.0, 1.5]
        assert layout.origin == [0.0, 0.0, 0.0]

    def test_grid_layout_requires_positive_dimensions(self) -> None:
        """Test that grid dimensions must be positive."""
        with pytest.raises(ValidationError):
            GridLayout(rows=0, cols=4, spacing=[1.0, 1.0])

    def test_random_layout(self) -> None:
        """Test creating a valid random layout."""
        layout = RandomLayout(center=[5.0, 5.0, 0.0], radius=3.0, count=10)
        assert layout.type == "random"
        assert layout.center == [5.0, 5.0, 0.0]
        assert layout.radius == 3.0
        assert layout.count == 10
        assert layout.random_yaw is True

    def test_random_layout_requires_positive_radius(self) -> None:
        """Test that radius must be positive."""
        with pytest.raises(ValidationError):
            RandomLayout(center=[0.0, 0.0, 0.0], radius=0.0, count=5)


class TestObjectSpec:
    """Tests for ObjectSpec model."""

    def test_object_with_instances(self) -> None:
        """Test object with explicit instances."""
        obj = ObjectSpec(
            asset_id="crate_wooden_small",
            instances=[
                InstanceSpec(pose=Pose(position=[0.0, 0.0, 0.0])),
                InstanceSpec(pose=Pose(position=[1.0, 0.0, 0.0])),
            ],
        )
        assert obj.asset_id == "crate_wooden_small"
        assert len(obj.instances) == 2

    def test_object_with_grid_layout(self) -> None:
        """Test object with grid layout."""
        obj = ObjectSpec(
            asset_id="crate_wooden_small",
            layout=GridLayout(rows=2, cols=3, spacing=[0.5, 0.5]),
        )
        assert obj.layout is not None
        assert obj.layout.type == "grid"

    def test_object_with_random_layout(self) -> None:
        """Test object with random layout."""
        obj = ObjectSpec(
            asset_id="crate_wooden_small",
            layout=RandomLayout(center=[0.0, 0.0, 0.0], radius=5.0, count=10),
        )
        assert obj.layout is not None
        assert obj.layout.type == "random"

    def test_object_cannot_have_both_layout_and_instances(self) -> None:
        """Test that layout and instances are mutually exclusive."""
        with pytest.raises(ValidationError, match="Cannot specify both"):
            ObjectSpec(
                asset_id="crate_wooden_small",
                layout=GridLayout(rows=2, cols=2, spacing=[1.0, 1.0]),
                instances=[InstanceSpec(pose=Pose(position=[0.0, 0.0, 0.0]))],
            )

    def test_object_with_neither_layout_nor_instances(self) -> None:
        """Test that an object can have neither (single default placement)."""
        obj = ObjectSpec(asset_id="tractor_bluewhite")
        assert obj.layout is None
        assert obj.instances is None


class TestCameraSpec:
    """Tests for CameraSpec model."""

    def test_camera_with_pose(self) -> None:
        """Test camera with pose only."""
        cam = CameraSpec(
            name="main_camera",
            pose=Pose(position=[0.0, 0.0, 5.0], pitch_deg=-45.0),
        )
        assert cam.name == "main_camera"
        assert cam.fovy == 45.0  # default

    def test_camera_with_target(self) -> None:
        """Test camera with look-at target."""
        cam = CameraSpec(
            name="tracking_camera",
            pose=Pose(position=[10.0, 10.0, 5.0]),
            target=[0.0, 0.0, 0.0],
        )
        assert cam.target == [0.0, 0.0, 0.0]

    def test_camera_fov_bounds(self) -> None:
        """Test that FOV must be in valid range."""
        with pytest.raises(ValidationError):
            CameraSpec(
                name="bad_camera",
                pose=Pose(position=[0.0, 0.0, 5.0]),
                fovy=200.0,  # Too high
            )


class TestSceneSpec:
    """Tests for the complete SceneSpec model."""

    def test_example_scene_spec_validates(self) -> None:
        """Test that example_scene_spec() creates a valid spec."""
        spec = example_scene_spec()
        assert isinstance(spec, SceneSpec)
        assert spec.name == "orchard_demo"
        assert spec.environment.asset_id == "orchard"
        assert len(spec.objects) == 3
        assert len(spec.cameras) == 2
        assert len(spec.lights) == 1

    def test_scene_spec_serialization_roundtrip(self) -> None:
        """Test that SceneSpec can be serialized and deserialized."""
        original = example_scene_spec()

        # Serialize to JSON
        json_str = original.model_dump_json()

        # Deserialize back
        restored = SceneSpec.model_validate_json(json_str)

        # Check equality
        assert restored.name == original.name
        assert restored.environment.asset_id == original.environment.asset_id
        assert len(restored.objects) == len(original.objects)
        assert len(restored.cameras) == len(original.cameras)

    def test_scene_spec_dict_roundtrip(self) -> None:
        """Test roundtrip via dict."""
        original = example_scene_spec()

        # Convert to dict
        data = original.model_dump()

        # Recreate from dict
        restored = SceneSpec.model_validate(data)

        assert restored.name == original.name

    def test_minimal_scene_spec(self) -> None:
        """Test creating a minimal valid scene."""
        spec = SceneSpec(
            name="minimal",
            environment=EnvironmentSpec(asset_id="orchard"),
        )
        assert spec.name == "minimal"
        assert spec.objects == []
        assert spec.cameras == []
        assert spec.physics.timestep == 0.002

    def test_scene_spec_from_json_string(self) -> None:
        """Test parsing SceneSpec from a JSON string."""
        json_str = """
        {
            "name": "test_scene",
            "environment": {
                "asset_id": "orchard"
            },
            "objects": [
                {
                    "asset_id": "crate_wooden_small",
                    "instances": [
                        {"pose": {"position": [1.0, 2.0, 0.0]}}
                    ]
                }
            ]
        }
        """
        spec = SceneSpec.model_validate_json(json_str)
        assert spec.name == "test_scene"
        assert len(spec.objects) == 1
        assert spec.objects[0].asset_id == "crate_wooden_small"


class TestPhysicsSpec:
    """Tests for PhysicsSpec model."""

    def test_default_physics(self) -> None:
        """Test default physics settings."""
        physics = PhysicsSpec()
        assert physics.timestep == 0.002
        assert physics.solver == "Newton"
        assert physics.iterations == 50

    def test_physics_timestep_bounds(self) -> None:
        """Test that timestep must be positive and reasonable."""
        with pytest.raises(ValidationError):
            PhysicsSpec(timestep=0.0)

        with pytest.raises(ValidationError):
            PhysicsSpec(timestep=0.5)  # Too large


class TestEnvironmentSpec:
    """Tests for EnvironmentSpec model."""

    def test_environment_defaults(self) -> None:
        """Test environment with defaults."""
        env = EnvironmentSpec(asset_id="orchard")
        assert env.gravity == [0.0, 0.0, -9.81]
        assert env.size is None

    def test_environment_custom_gravity(self) -> None:
        """Test environment with custom gravity (e.g., moon)."""
        env = EnvironmentSpec(asset_id="moon_surface", gravity=[0.0, 0.0, -1.62])
        assert env.gravity == [0.0, 0.0, -1.62]


class TestLightSpec:
    """Tests for LightSpec model."""

    def test_directional_light(self) -> None:
        """Test creating a directional light."""
        light = LightSpec(
            name="sun",
            type="directional",
            direction=[0.0, 0.0, -1.0],
        )
        assert light.type == "directional"
        assert light.diffuse == [1.0, 1.0, 1.0]

    def test_point_light(self) -> None:
        """Test creating a point light."""
        light = LightSpec(
            name="lamp",
            type="point",
            position=[5.0, 5.0, 3.0],
        )
        assert light.type == "point"

