# Asset Manifest Specification

## Overview

Each asset in Neoscene is described by a `manifest.json` file that provides metadata for discovery, placement, and semantic matching.

## Schema

```json
{
  "asset_id": "string (required)",
  "name": "string (required)",
  "category": "environment | robot | prop | sensor (required)",
  "tags": ["array", "of", "strings"],
  "mjcf_include": "string - relative path to MJCF file (required)",
  "physical_size": [x, y, z] | null,
  "placement_rules": {
    "allow_on": ["ground", "table", "shelf"],
    "min_clearance": 0.0
  },
  "semantics": {
    "human_names": ["crate", "box", "container"],
    "usage": ["storage", "logistics"]
  },
  "extra": {}
}
```

## Field Descriptions

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `asset_id` | string | Unique identifier, should match folder name |
| `name` | string | Human-readable display name |
| `category` | enum | One of: `environment`, `robot`, `prop`, `sensor` |
| `mjcf_include` | string | Relative path to the MJCF XML file |

### Optional Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `tags` | string[] | `[]` | Searchable tags for categorization |
| `physical_size` | float[3] | `null` | Bounding box dimensions [x, y, z] in meters |
| `placement_rules` | object | `{}` | Rules for valid placement |
| `semantics` | object | `{}` | Natural language matching data |
| `extra` | object | `{}` | Extension field for custom metadata |

### Placement Rules

```json
{
  "allow_on": ["ground", "table", "shelf", "robot"],
  "min_clearance": 0.05
}
```

- `allow_on`: List of surface types where this asset can be placed
- `min_clearance`: Minimum distance (meters) required from other objects

### Semantics

```json
{
  "human_names": ["tractor", "farm vehicle", "agricultural vehicle"],
  "usage": ["farming", "agriculture", "hauling"]
}
```

- `human_names`: Alternative names users might use to refer to this asset
- `usage`: Typical use cases or contexts

## Examples

### Environment

```json
{
  "asset_id": "orchard",
  "name": "Apple Orchard",
  "category": "environment",
  "tags": ["outdoor", "farm", "trees", "agriculture"],
  "mjcf_include": "mjcf/orchard.xml",
  "physical_size": [100.0, 100.0, 10.0],
  "placement_rules": {},
  "semantics": {
    "human_names": ["orchard", "apple farm", "fruit garden"],
    "usage": ["agriculture", "farming", "outdoor"]
  }
}
```

### Robot

```json
{
  "asset_id": "tractor_bluewhite",
  "name": "Blue & White Tractor",
  "category": "robot",
  "tags": ["vehicle", "tractor", "farm", "wheeled"],
  "mjcf_include": "mjcf/tractor_bluewhite.xml",
  "physical_size": [4.0, 2.0, 2.5],
  "placement_rules": {
    "allow_on": ["ground"],
    "min_clearance": 0.5
  },
  "semantics": {
    "human_names": ["tractor", "farm tractor", "blue tractor"],
    "usage": ["farming", "hauling", "agriculture"]
  }
}
```

### Prop

```json
{
  "asset_id": "crate_wooden_small",
  "name": "Small Wooden Crate",
  "category": "prop",
  "tags": ["crate", "box", "wood", "stackable"],
  "mjcf_include": "mjcf/crate_wooden_small.xml",
  "physical_size": [0.6, 0.4, 0.4],
  "placement_rules": {
    "allow_on": ["ground", "table", "shelf", "crate"],
    "min_clearance": 0.02
  },
  "semantics": {
    "human_names": ["crate", "box", "wooden crate", "wooden box"],
    "usage": ["logistics", "storage"]
  }
}
```

### Sensor

```json
{
  "asset_id": "cam_top_down",
  "name": "Top-Down Camera",
  "category": "sensor",
  "tags": ["camera", "sensor", "vision", "overhead"],
  "mjcf_include": "mjcf/cam_top_down.xml",
  "placement_rules": {
    "allow_on": ["ceiling", "mount"],
    "min_clearance": 0.0
  },
  "semantics": {
    "human_names": ["top camera", "overhead camera", "bird's eye camera"],
    "usage": ["monitoring", "surveillance", "tracking"]
  }
}
```

## Directory Layout

```
neoscene/assets/
├── environments/
│   └── orchard/
│       ├── manifest.json
│       ├── meshes/
│       ├── textures/
│       └── mjcf/
│           └── orchard.xml
├── robots/
│   └── tractor_bluewhite/
│       ├── manifest.json
│       ├── meshes/
│       └── mjcf/
│           └── tractor_bluewhite.xml
├── props/
│   └── crate_wooden_small/
│       ├── manifest.json
│       ├── meshes/
│       └── mjcf/
│           └── crate_wooden_small.xml
└── sensors/
    └── cam_top_down/
        ├── manifest.json
        └── mjcf/
            └── cam_top_down.xml
```

