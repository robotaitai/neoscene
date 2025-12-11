"""Scene specification schema - the intermediate representation (IR).

This module defines the SceneSpec schema that serves as the bridge between
natural language scene descriptions (via LLM) and MuJoCo MJCF output.

The LLM generates JSON conforming to SceneSpec, which the exporter then
converts to valid MJCF XML.
"""

import json
from pathlib import Path
from typing import Annotated, List, Literal, Optional, Union

from pydantic import BaseModel, Field, model_validator


class Pose(BaseModel):
    """3D pose specification with position and orientation.

    Orientation is specified using Euler angles in degrees for human readability.
    The order of rotations is yaw (Z) -> pitch (Y) -> roll (X).
    """

    position: Annotated[List[float], Field(min_length=3, max_length=3)] = Field(
        description="[x, y, z] position in meters"
    )
    yaw_deg: float = Field(default=0.0, description="Rotation around Z-axis in degrees")
    pitch_deg: float = Field(default=0.0, description="Rotation around Y-axis in degrees")
    roll_deg: float = Field(default=0.0, description="Rotation around X-axis in degrees")


class GridLayout(BaseModel):
    """Layout objects in a regular grid pattern.

    Objects are placed starting from origin, with spacing between each.
    Total count = rows * cols.
    """

    type: Literal["grid"] = "grid"
    origin: Annotated[List[float], Field(min_length=3, max_length=3)] = Field(
        default_factory=lambda: [0.0, 0.0, 0.0],
        description="[x, y, z] starting position of the grid",
    )
    rows: int = Field(ge=1, description="Number of rows in the grid")
    cols: int = Field(ge=1, description="Number of columns in the grid")
    spacing: Annotated[List[float], Field(min_length=2, max_length=2)] = Field(
        description="[dx, dy] spacing between objects in meters"
    )
    yaw_variation_deg: float = Field(
        default=0.0, description="Random yaw variation per object in degrees"
    )


class RandomLayout(BaseModel):
    """Layout objects randomly within a circular area.

    Objects are placed randomly within a circle centered at 'center' with
    the given radius. The z-coordinate from center is used for all objects.
    """

    type: Literal["random"] = "random"
    center: Annotated[List[float], Field(min_length=3, max_length=3)] = Field(
        description="[x, y, z] center of the spawn area"
    )
    radius: float = Field(gt=0, description="Radius of the spawn area in meters")
    count: int = Field(ge=1, description="Number of objects to spawn")
    min_separation: float = Field(
        default=0.0, description="Minimum distance between objects in meters"
    )
    random_yaw: bool = Field(default=True, description="Randomize yaw orientation")


class InstanceSpec(BaseModel):
    """Explicit instance specification with a fixed pose."""

    pose: Pose = Field(description="Exact pose for this instance")
    name_suffix: Optional[str] = Field(
        default=None, description="Optional suffix for the instance name"
    )


class ObjectSpec(BaseModel):
    """Specification for placing one or more instances of an asset.

    Objects can be placed using:
    - Explicit instances: Provide a list of InstanceSpec with exact poses
    - Grid layout: Place objects in a regular grid pattern
    - Random layout: Place objects randomly in an area

    Exactly one of (instances, layout) must be provided, or neither for a
    single object at the default pose.
    """

    asset_id: str = Field(description="ID of the asset from the catalog")
    name: Optional[str] = Field(
        default=None, description="Optional name override for the object(s)"
    )
    layout: Optional[Union[GridLayout, RandomLayout]] = Field(
        default=None, description="Layout pattern for multiple objects"
    )
    instances: Optional[List[InstanceSpec]] = Field(
        default=None, description="Explicit list of instance poses"
    )

    @model_validator(mode="after")
    def validate_placement(self) -> "ObjectSpec":
        """Ensure only one placement method is specified."""
        if self.layout is not None and self.instances is not None:
            raise ValueError("Cannot specify both 'layout' and 'instances'")
        return self


class CameraSpec(BaseModel):
    """Camera specification for scene observation.

    Cameras can be specified with a pose, or aimed at a target point.
    If asset_id is provided, it references a sensor asset from the catalog.
    """

    name: str = Field(description="Unique name for the camera")
    asset_id: Optional[str] = Field(
        default=None, description="Optional sensor asset ID from catalog"
    )
    pose: Pose = Field(description="Camera pose in world coordinates")
    target: Optional[Annotated[List[float], Field(min_length=3, max_length=3)]] = Field(
        default=None, description="Optional [x, y, z] look-at target point"
    )
    fovy: float = Field(default=45.0, ge=1.0, le=180.0, description="Vertical FOV in degrees")


class LightSpec(BaseModel):
    """Light specification for scene illumination."""

    name: str = Field(description="Unique name for the light")
    type: Literal["directional", "point", "spot"] = Field(
        default="directional", description="Type of light source"
    )
    position: Annotated[List[float], Field(min_length=3, max_length=3)] = Field(
        default_factory=lambda: [0.0, 0.0, 10.0],
        description="[x, y, z] position of the light",
    )
    direction: Optional[Annotated[List[float], Field(min_length=3, max_length=3)]] = Field(
        default=None, description="[dx, dy, dz] direction for directional/spot lights"
    )
    diffuse: Annotated[List[float], Field(min_length=3, max_length=3)] = Field(
        default_factory=lambda: [1.0, 1.0, 1.0],
        description="[r, g, b] diffuse color (0-1)",
    )
    specular: Annotated[List[float], Field(min_length=3, max_length=3)] = Field(
        default_factory=lambda: [0.5, 0.5, 0.5],
        description="[r, g, b] specular color (0-1)",
    )


class EnvironmentSpec(BaseModel):
    """Environment/world specification.

    Defines the base environment asset and global settings like gravity.
    """

    asset_id: str = Field(description="ID of the environment asset from catalog")
    size: Optional[Annotated[List[float], Field(min_length=3, max_length=3)]] = Field(
        default=None, description="Optional [x, y, z] size override in meters"
    )
    gravity: Annotated[List[float], Field(min_length=3, max_length=3)] = Field(
        default_factory=lambda: [0.0, 0.0, -9.81],
        description="Gravity vector [gx, gy, gz] in m/s²",
    )


class PhysicsSpec(BaseModel):
    """Physics simulation settings."""

    timestep: float = Field(
        default=0.002, gt=0, le=0.1, description="Simulation timestep in seconds"
    )
    solver: Literal["PGS", "CG", "Newton"] = Field(
        default="Newton", description="Constraint solver type"
    )
    iterations: int = Field(default=50, ge=1, description="Solver iterations per step")
    integrator: Literal["Euler", "RK4", "implicit", "implicitfast"] = Field(
        default="implicitfast", description="Numerical integrator"
    )


class SceneSpec(BaseModel):
    """Complete scene specification - the intermediate representation (IR).

    This is the main schema that the LLM generates and the exporter consumes.
    It fully describes a MuJoCo scene including environment, objects, cameras,
    lights, and physics settings.

    Example:
        >>> spec = SceneSpec(
        ...     name="orchard_scene",
        ...     environment=EnvironmentSpec(asset_id="orchard"),
        ...     objects=[
        ...         ObjectSpec(asset_id="tractor_bluewhite", instances=[
        ...             InstanceSpec(pose=Pose(position=[5.0, 0.0, 0.0]))
        ...         ])
        ...     ]
        ... )
    """

    name: str = Field(description="Unique name for the scene")
    description: Optional[str] = Field(
        default=None, description="Human-readable description of the scene"
    )
    environment: EnvironmentSpec = Field(description="Environment/world specification")
    objects: List[ObjectSpec] = Field(
        default_factory=list, description="List of objects to place in the scene"
    )
    cameras: List[CameraSpec] = Field(
        default_factory=list, description="List of cameras in the scene"
    )
    lights: List[LightSpec] = Field(
        default_factory=list, description="Additional lights (beyond environment default)"
    )
    physics: PhysicsSpec = Field(
        default_factory=PhysicsSpec, description="Physics simulation settings"
    )


def example_scene_spec() -> SceneSpec:
    """Create an example SceneSpec for testing and documentation.

    Returns:
        A complete SceneSpec representing an orchard scene with a tractor,
        some crates, and a camera.
    """
    return SceneSpec(
        name="orchard_demo",
        description="A demonstration scene with an orchard, tractor, and crates",
        environment=EnvironmentSpec(
            asset_id="orchard",
            gravity=[0.0, 0.0, -9.81],
        ),
        objects=[
            # Single tractor at a specific position
            ObjectSpec(
                asset_id="tractor_bluewhite",
                name="main_tractor",
                instances=[
                    InstanceSpec(
                        pose=Pose(position=[5.0, 2.0, 0.0], yaw_deg=45.0),
                        name_suffix="1",
                    )
                ],
            ),
            # Grid of crates
            ObjectSpec(
                asset_id="crate_wooden_small",
                name="storage_crates",
                layout=GridLayout(
                    origin=[-3.0, -3.0, 0.0],
                    rows=2,
                    cols=3,
                    spacing=[0.8, 0.6],
                ),
            ),
            # Random scattered crates
            ObjectSpec(
                asset_id="crate_wooden_small",
                name="scattered_crates",
                layout=RandomLayout(
                    center=[10.0, 10.0, 0.0],
                    radius=5.0,
                    count=5,
                    min_separation=1.0,
                ),
            ),
        ],
        cameras=[
            CameraSpec(
                name="overview_cam",
                asset_id="cam_top_down",
                pose=Pose(position=[0.0, 0.0, 15.0], pitch_deg=-90.0),
                fovy=60.0,
            ),
            CameraSpec(
                name="tractor_cam",
                pose=Pose(position=[8.0, 5.0, 2.0]),
                target=[5.0, 2.0, 1.0],
                fovy=45.0,
            ),
        ],
        lights=[
            LightSpec(
                name="sun",
                type="directional",
                position=[0.0, 0.0, 20.0],
                direction=[0.5, 0.5, -1.0],
                diffuse=[1.0, 0.95, 0.9],
            ),
        ],
        physics=PhysicsSpec(
            timestep=0.002,
            solver="Newton",
            iterations=50,
        ),
    )


def export_json_schema(output_path: Path) -> None:
    """Export the SceneSpec JSON schema to a file.

    Args:
        output_path: Path to write the JSON schema file.
    """
    schema = SceneSpec.model_json_schema()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(schema, indent=2))

