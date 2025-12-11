"""MJCF exporter - converts SceneSpec to MuJoCo XML.

This module provides functionality to convert the SceneSpec intermediate
representation into valid MJCF XML that can be loaded by MuJoCo.
"""

import math
import random
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Tuple
from xml.dom import minidom

from neoscene.core.asset_catalog import AssetCatalog
from neoscene.core.scene_schema import (
    GridLayout,
    InstanceSpec,
    ObjectSpec,
    Pose,
    RandomLayout,
    SceneSpec,
)


def _deg_to_rad(deg: float) -> float:
    """Convert degrees to radians."""
    return deg * math.pi / 180.0


def _to_euler_deg(pose: Pose) -> Tuple[float, float, float]:
    """Extract Euler angles from a Pose in degrees.

    MuJoCo uses euler="roll pitch yaw" order in degrees by default.

    Args:
        pose: The Pose object with yaw_deg, pitch_deg, roll_deg.

    Returns:
        Tuple of (roll, pitch, yaw) in degrees.
    """
    return (pose.roll_deg, pose.pitch_deg, pose.yaw_deg)


def _format_vec(values: List[float], precision: int = 4) -> str:
    """Format a list of floats as a space-separated string.

    Args:
        values: List of float values.
        precision: Decimal precision for formatting.

    Returns:
        Space-separated string of values.
    """
    return " ".join(f"{v:.{precision}g}" for v in values)


def _layout_instances(
    obj: ObjectSpec,
    catalog: AssetCatalog,
    seed: int = 42,
) -> List[InstanceSpec]:
    """Generate instance specifications from an ObjectSpec.

    Handles explicit instances, grid layouts, and random layouts.

    Args:
        obj: The ObjectSpec to process.
        catalog: Asset catalog for looking up asset info.
        seed: Random seed for reproducible random layouts.

    Returns:
        List of InstanceSpec objects with resolved poses.

    TODO(future): Add collision detection to prevent overlapping objects
    TODO(future): Use physical_size from manifest for smarter spacing
    TODO(future): Support constraint-based layouts (e.g., "near", "on top of")
    """
    # If explicit instances provided, use them
    if obj.instances is not None:
        return obj.instances

    # If no layout, create single instance at origin
    if obj.layout is None:
        return [InstanceSpec(pose=Pose(position=[0.0, 0.0, 0.0]))]

    instances: List[InstanceSpec] = []

    if isinstance(obj.layout, GridLayout):
        layout = obj.layout
        rng = random.Random(seed)

        for row in range(layout.rows):
            for col in range(layout.cols):
                x = layout.origin[0] + col * layout.spacing[0]
                y = layout.origin[1] + row * layout.spacing[1]
                z = layout.origin[2]

                # Apply optional yaw variation
                yaw = 0.0
                if layout.yaw_variation_deg > 0:
                    yaw = rng.uniform(-layout.yaw_variation_deg, layout.yaw_variation_deg)

                instances.append(
                    InstanceSpec(
                        pose=Pose(position=[x, y, z], yaw_deg=yaw),
                        name_suffix=f"r{row}_c{col}",
                    )
                )

    elif isinstance(obj.layout, RandomLayout):
        layout = obj.layout
        rng = random.Random(seed)

        placed_positions: List[Tuple[float, float]] = []

        for i in range(layout.count):
            # Try to find a valid position
            max_attempts = 100
            for _ in range(max_attempts):
                # Random point in circle
                angle = rng.uniform(0, 2 * math.pi)
                r = math.sqrt(rng.uniform(0, 1)) * layout.radius
                x = layout.center[0] + r * math.cos(angle)
                y = layout.center[1] + r * math.sin(angle)

                # Check minimum separation
                if layout.min_separation > 0:
                    too_close = False
                    for px, py in placed_positions:
                        dist = math.sqrt((x - px) ** 2 + (y - py) ** 2)
                        if dist < layout.min_separation:
                            too_close = True
                            break
                    if too_close:
                        continue

                placed_positions.append((x, y))
                break

            z = layout.center[2]
            yaw = rng.uniform(0, 360) if layout.random_yaw else 0.0

            instances.append(
                InstanceSpec(
                    pose=Pose(position=[x, y, z], yaw_deg=yaw),
                    name_suffix=f"{i}",
                )
            )

    return instances


def _compute_look_at_euler(
    position: List[float],
    target: List[float],
) -> Tuple[float, float, float]:
    """Compute Euler angles to look from position toward target.

    Args:
        position: Camera position [x, y, z].
        target: Target point [x, y, z].

    Returns:
        Tuple of (roll, pitch, yaw) in degrees.
    """
    dx = target[0] - position[0]
    dy = target[1] - position[1]
    dz = target[2] - position[2]

    # Yaw: rotation around Z axis (horizontal direction)
    yaw = math.atan2(dy, dx) * 180 / math.pi

    # Pitch: rotation around Y axis (vertical direction)
    horizontal_dist = math.sqrt(dx * dx + dy * dy)
    pitch = -math.atan2(dz, horizontal_dist) * 180 / math.pi

    return (0.0, pitch, yaw)


def _load_asset_content(mjcf_path: Path, prefix: str) -> dict:
    """Load asset MJCF content and extract worldbody/sensor elements.

    Args:
        mjcf_path: Path to the asset MJCF file.
        prefix: Prefix to add to element names for uniqueness.

    Returns:
        Dictionary with 'worldbody' (list of body elements) and 'sensors' (list of sensor elements).
    """
    content = mjcf_path.read_text()

    # Remove XML comments
    content = re.sub(r"<!--.*?-->", "", content, flags=re.DOTALL)
    content = content.strip()

    result = {"worldbody": [], "sensors": [], "assets": []}

    if not content:
        return result

    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        return result

    # Build a mapping of original names to prefixed names for this asset
    name_map = {}
    
    def collect_names(elem: ET.Element):
        """Collect all name attributes for later renaming."""
        if "name" in elem.attrib:
            name_map[elem.get("name")] = f"{prefix}_{elem.get('name')}"
        for child in elem:
            collect_names(child)
    
    def rename_recursive(elem: ET.Element):
        """Recursively rename all 'name' and reference attributes with prefix."""
        # Rename the name attribute
        if "name" in elem.attrib and elem.get("name") in name_map:
            elem.set("name", name_map[elem.get("name")])
        
        # Rename reference attributes (site, material, mesh, texture, etc.)
        for ref_attr in ["site", "material", "mesh", "texture", "class", "childclass"]:
            if ref_attr in elem.attrib:
                old_ref = elem.get(ref_attr)
                if old_ref in name_map:
                    elem.set(ref_attr, name_map[old_ref])
        
        for child in elem:
            rename_recursive(child)

    # Handle <mujoco> root element
    if root.tag == "mujoco":
        # First pass: collect all names from the entire tree
        for section in [root.find("asset"), root.find("worldbody"), root.find("sensor")]:
            if section is not None:
                collect_names(section)
        
        # Second pass: extract and rename
        # Extract asset elements (materials, textures, meshes)
        asset_elem = root.find("asset")
        if asset_elem is not None:
            for child in asset_elem:
                rename_recursive(child)
                result["assets"].append(child)
        
        # Extract worldbody children
        worldbody = root.find("worldbody")
        if worldbody is not None:
            for child in worldbody:
                rename_recursive(child)
                result["worldbody"].append(child)
        
        # Extract sensor elements
        sensor_elem = root.find("sensor")
        if sensor_elem is not None:
            for child in sensor_elem:
                rename_recursive(child)
                result["sensors"].append(child)
    else:
        # Legacy: treat as raw elements
        collect_names(root)
        rename_recursive(root)
        result["worldbody"].append(root)

    return result


def scene_to_mjcf(
    scene: SceneSpec,
    catalog: AssetCatalog,
    seed: int = 42,
) -> str:
    """Build a full MJCF XML string for the given scene.

    Args:
        scene: The SceneSpec to convert.
        catalog: Asset catalog for resolving asset paths.
        seed: Random seed for reproducible layouts.

    Returns:
        Complete MJCF XML string.
    """
    # Create root mujoco element
    mujoco = ET.Element("mujoco", model=scene.name)

    # Add compiler settings
    compiler = ET.SubElement(mujoco, "compiler")
    compiler.set("angle", "degree")
    compiler.set("coordinate", "local")

    # Add physics options
    option = ET.SubElement(mujoco, "option")
    option.set("timestep", str(scene.physics.timestep))
    option.set("iterations", str(scene.physics.iterations))
    option.set("solver", scene.physics.solver)
    option.set("integrator", scene.physics.integrator)
    option.set("gravity", _format_vec(scene.environment.gravity))

    # Add visual settings
    visual = ET.SubElement(mujoco, "visual")
    headlight = ET.SubElement(visual, "headlight")
    headlight.set("diffuse", "0.6 0.6 0.6")
    headlight.set("ambient", "0.3 0.3 0.3")

    # Create asset section for meshes/textures if needed
    asset = ET.SubElement(mujoco, "asset")
    # Add a default texture and material
    ET.SubElement(
        asset,
        "texture",
        name="grid",
        type="2d",
        builtin="checker",
        width="512",
        height="512",
        rgb1="0.2 0.3 0.4",
        rgb2="0.1 0.2 0.3",
    )
    ET.SubElement(
        asset,
        "material",
        name="grid_mat",
        texture="grid",
        texrepeat="8 8",
        reflectance="0.2",
    )

    # Create worldbody
    worldbody = ET.SubElement(mujoco, "worldbody")

    # Add default light if no lights specified
    if not scene.lights:
        light = ET.SubElement(worldbody, "light")
        light.set("name", "default_light")
        light.set("pos", "0 0 10")
        light.set("dir", "0 0 -1")
        light.set("diffuse", "1 1 1")
    else:
        # Add specified lights
        for light_spec in scene.lights:
            light = ET.SubElement(worldbody, "light")
            light.set("name", light_spec.name)
            light.set("pos", _format_vec(light_spec.position))
            if light_spec.direction:
                light.set("dir", _format_vec(light_spec.direction))
            light.set("diffuse", _format_vec(light_spec.diffuse))
            light.set("specular", _format_vec(light_spec.specular))
            if light_spec.type == "directional":
                light.set("directional", "true")

    # Collect all sensors from assets
    all_sensors = []

    # Add environment
    env_manifest = catalog.get(scene.environment.asset_id)
    env_path = catalog.get_path(scene.environment.asset_id)
    env_mjcf_path = (env_path / env_manifest.mjcf_include).resolve()

    env_body = ET.SubElement(worldbody, "body")
    env_body.set("name", f"env_{scene.environment.asset_id}")
    env_body.set("pos", "0 0 0")

    # Load and inline environment content
    env_content = _load_asset_content(env_mjcf_path, f"env_{scene.environment.asset_id}")
    for elem in env_content["worldbody"]:
        env_body.append(elem)
    for elem in env_content["assets"]:
        asset.append(elem)
    all_sensors.extend(env_content["sensors"])

    # Add objects
    for obj in scene.objects:
        obj_manifest = catalog.get(obj.asset_id)
        obj_path = catalog.get_path(obj.asset_id)
        obj_mjcf_path = (obj_path / obj_manifest.mjcf_include).resolve()

        instances = _layout_instances(obj, catalog, seed)
        obj_name_base = obj.name or obj.asset_id

        for idx, inst in enumerate(instances):
            body = ET.SubElement(worldbody, "body")

            # Generate unique name
            if inst.name_suffix:
                body_name = f"{obj_name_base}_{inst.name_suffix}"
            else:
                body_name = f"{obj_name_base}_{idx}"
            body.set("name", body_name)

            # Set position
            body.set("pos", _format_vec(inst.pose.position))

            # Set orientation if non-zero
            roll, pitch, yaw = _to_euler_deg(inst.pose)
            if roll != 0 or pitch != 0 or yaw != 0:
                body.set("euler", _format_vec([roll, pitch, yaw]))

            # Load and inline object content
            obj_content = _load_asset_content(obj_mjcf_path, body_name)
            for elem in obj_content["worldbody"]:
                body.append(elem)
            for elem in obj_content["assets"]:
                asset.append(elem)
            all_sensors.extend(obj_content["sensors"])

    # Add cameras
    for cam in scene.cameras:
        camera = ET.SubElement(worldbody, "camera")
        camera.set("name", cam.name)
        camera.set("pos", _format_vec(cam.pose.position))
        camera.set("fovy", str(cam.fovy))

        # Compute orientation
        if cam.target:
            roll, pitch, yaw = _compute_look_at_euler(cam.pose.position, cam.target)
            camera.set("euler", _format_vec([roll, pitch, yaw]))
        else:
            roll, pitch, yaw = _to_euler_deg(cam.pose)
            if roll != 0 or pitch != 0 or yaw != 0:
                camera.set("euler", _format_vec([roll, pitch, yaw]))

    # Add sensors section if we have any
    if all_sensors:
        sensor_section = ET.SubElement(mujoco, "sensor")
        for sensor_elem in all_sensors:
            sensor_section.append(sensor_elem)

    # Convert to string with pretty printing
    rough_string = ET.tostring(mujoco, encoding="unicode")
    reparsed = minidom.parseString(rough_string)
    pretty_xml = reparsed.toprettyxml(indent="  ")

    # Remove the XML declaration line for cleaner output
    lines = pretty_xml.split("\n")
    if lines[0].startswith("<?xml"):
        lines = lines[1:]
    # Remove empty lines
    lines = [line for line in lines if line.strip()]

    return "\n".join(lines)


def write_scene_to_file(
    scene: SceneSpec,
    catalog: AssetCatalog,
    path: Path,
    seed: int = 42,
) -> None:
    """Write a scene to an MJCF XML file.

    Args:
        scene: The SceneSpec to convert.
        catalog: Asset catalog for resolving asset paths.
        path: Output file path.
        seed: Random seed for reproducible layouts.
    """
    xml_content = scene_to_mjcf(scene, catalog, seed)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(xml_content)
