# SceneSpec - Scene Intermediate Representation

## Overview

SceneSpec is the intermediate representation (IR) between natural language scene descriptions and MuJoCo MJCF output. The LLM generates JSON conforming to SceneSpec, which the exporter converts to valid MJCF XML.

## Schema Components

### SceneSpec (Root)

The top-level scene specification.

```json
{
  "name": "scene_name",
  "description": "Optional human-readable description",
  "environment": { ... },
  "objects": [ ... ],
  "cameras": [ ... ],
  "lights": [ ... ],
  "physics": { ... }
}
```

### EnvironmentSpec

Defines the base environment and global settings.

```json
{
  "asset_id": "orchard",
  "size": [100.0, 100.0, 10.0],
  "gravity": [0.0, 0.0, -9.81]
}
```

### ObjectSpec

Specifies one or more instances of an asset. Use ONE of:
- `instances`: Explicit list of poses
- `layout`: Grid or random placement pattern
- Neither: Single object at default position

```json
{
  "asset_id": "crate_wooden_small",
  "name": "storage_crates",
  "layout": {
    "type": "grid",
    "origin": [0.0, 0.0, 0.0],
    "rows": 3,
    "cols": 4,
    "spacing": [0.8, 0.6]
  }
}
```

### Pose

3D position and orientation using Euler angles.

```json
{
  "position": [5.0, 2.0, 0.0],
  "yaw_deg": 45.0,
  "pitch_deg": 0.0,
  "roll_deg": 0.0
}
```

### Layout Types

#### GridLayout

```json
{
  "type": "grid",
  "origin": [0.0, 0.0, 0.0],
  "rows": 2,
  "cols": 3,
  "spacing": [1.0, 1.0],
  "yaw_variation_deg": 0.0
}
```

#### RandomLayout

```json
{
  "type": "random",
  "center": [10.0, 10.0, 0.0],
  "radius": 5.0,
  "count": 10,
  "min_separation": 0.5,
  "random_yaw": true
}
```

### CameraSpec

```json
{
  "name": "main_camera",
  "asset_id": "cam_top_down",
  "pose": {
    "position": [0.0, 0.0, 15.0],
    "pitch_deg": -90.0
  },
  "target": [0.0, 0.0, 0.0],
  "fovy": 60.0
}
```

### LightSpec

```json
{
  "name": "sun",
  "type": "directional",
  "position": [0.0, 0.0, 20.0],
  "direction": [0.5, 0.5, -1.0],
  "diffuse": [1.0, 0.95, 0.9],
  "specular": [0.5, 0.5, 0.5]
}
```

### PhysicsSpec

```json
{
  "timestep": 0.002,
  "solver": "Newton",
  "iterations": 50,
  "integrator": "implicitfast"
}
```

## Complete Example

```json
{
  "name": "orchard_demo",
  "description": "An orchard with a tractor and crates",
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
            "position": [5.0, 2.0, 0.0],
            "yaw_deg": 45.0
          }
        }
      ]
    },
    {
      "asset_id": "crate_wooden_small",
      "name": "storage_crates",
      "layout": {
        "type": "grid",
        "origin": [-3.0, -3.0, 0.0],
        "rows": 2,
        "cols": 3,
        "spacing": [0.8, 0.6]
      }
    }
  ],
  "cameras": [
    {
      "name": "overview",
      "pose": {
        "position": [0.0, 0.0, 15.0],
        "pitch_deg": -90.0
      },
      "fovy": 60.0
    }
  ],
  "physics": {
    "timestep": 0.002,
    "solver": "Newton"
  }
}
```

## Usage in Python

```python
from neoscene.core.scene_schema import SceneSpec, example_scene_spec

# Create from example
spec = example_scene_spec()

# Serialize to JSON
json_str = spec.model_dump_json(indent=2)

# Parse from JSON
spec = SceneSpec.model_validate_json(json_str)

# Access components
print(spec.environment.asset_id)  # "orchard"
print(len(spec.objects))          # 3
```

## JSON Schema

The full JSON Schema is available at `config/scene_spec.schema.json`.

```python
from neoscene.core.scene_schema import SceneSpec

# Get JSON Schema
schema = SceneSpec.model_json_schema()
```

