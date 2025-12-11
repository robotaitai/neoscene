# Adding New Assets to Neoscene

This guide explains how to add new assets to the Neoscene catalog.

## Asset Structure

Each asset lives in a category folder under `neoscene/assets/`:

```
neoscene/assets/
├── environments/    # Base scenes (terrains, rooms)
├── robots/          # Controllable agents
├── props/           # Static objects
└── sensors/         # Cameras, lidars, etc.
```

## Creating a New Asset

### 1. Create the Asset Folder

```bash
mkdir -p neoscene/assets/props/my_new_asset/{meshes,textures,mjcf}
```

### 2. Add the Mesh Files (Optional)

Place your 3D models in the `meshes/` folder:
- Supported formats: OBJ, STL (for MuJoCo)
- Include textures in `textures/` if needed

### 3. Create the MJCF Fragment

Create `mjcf/my_new_asset.xml` with the geometry:

```xml
<!-- my_new_asset - includable fragment -->
<geom name="body" type="box" size="0.5 0.3 0.2" rgba="0.6 0.4 0.2 1" mass="5"/>
```

**Important**: This file should contain only the content that goes inside a `<body>` element - no `<mujoco>` wrapper.

### 4. Create the Manifest

Create `manifest.json`:

```json
{
  "asset_id": "my_new_asset",
  "name": "My New Asset",
  "category": "prop",
  "tags": ["custom", "example"],
  "mjcf_include": "mjcf/my_new_asset.xml",
  "physical_size": [1.0, 0.6, 0.4],
  "placement_rules": {
    "allow_on": ["ground", "table"],
    "min_clearance": 0.1
  },
  "semantics": {
    "human_names": ["my asset", "custom thing"],
    "usage": ["testing", "demonstration"]
  },
  "extra": {}
}
```

## Manifest Fields Reference

| Field | Required | Description |
|-------|----------|-------------|
| `asset_id` | Yes | Unique identifier (must match folder name) |
| `name` | Yes | Human-readable display name |
| `category` | Yes | One of: environment, robot, prop, sensor |
| `tags` | No | Searchable keywords |
| `mjcf_include` | Yes | Path to MJCF fragment (relative to asset folder) |
| `physical_size` | No | Bounding box [x, y, z] in meters |
| `placement_rules.allow_on` | No | Surface types where asset can be placed |
| `placement_rules.min_clearance` | No | Minimum distance from other objects |
| `semantics.human_names` | No | Alternative names for LLM matching |
| `semantics.usage` | No | Typical use cases |

## Validating Your Asset

### 1. Check the Manifest

```python
from pathlib import Path
from neoscene.core.asset_manifest import load_manifest

manifest = load_manifest(Path("neoscene/assets/props/my_new_asset/manifest.json"))
print(f"Loaded: {manifest.name}")
```

### 2. Check the Catalog

```python
from pathlib import Path
from neoscene.core.asset_catalog import AssetCatalog

catalog = AssetCatalog(Path("neoscene/assets"))
print(f"Total assets: {len(catalog)}")

# Search for your asset
results = catalog.search("my asset")
print(f"Found: {[r.asset_id for r in results]}")
```

### 3. Test in a Scene

Create a test scene JSON:

```json
{
  "name": "test_my_asset",
  "environment": {"asset_id": "orchard"},
  "objects": [
    {
      "asset_id": "my_new_asset",
      "instances": [{"pose": {"position": [0, 0, 0.5]}}]
    }
  ],
  "cameras": [
    {"name": "cam", "pose": {"position": [3, 3, 2]}, "target": [0, 0, 0.5]}
  ]
}
```

Run it:

```bash
python -m neoscene.app.main --scene-json test_scene.json
```

## Tips

### For Complex Meshes

If you have detailed 3D models:

1. Simplify the collision geometry (use primitives)
2. Keep visual meshes for rendering (future feature)
3. Reference mesh files in the MJCF:

```xml
<geom name="visual" type="mesh" mesh="my_mesh"/>
```

### For Articulated Robots

Robots with joints need more complex MJCF:

```xml
<body name="base">
  <geom name="chassis" type="box" size="0.5 0.3 0.1"/>
  <body name="arm" pos="0.3 0 0.1">
    <joint name="shoulder" type="hinge" axis="0 1 0"/>
    <geom name="arm_link" type="capsule" size="0.05" fromto="0 0 0 0.3 0 0"/>
  </body>
</body>
```

### Semantic Matching

Add good `human_names` for LLM matching:

```json
"semantics": {
  "human_names": [
    "wooden barrel",
    "barrel",
    "wine barrel",
    "oak barrel",
    "storage barrel"
  ],
  "usage": ["storage", "decoration", "winery", "medieval"]
}
```

## Troubleshooting

### Asset Not Found

- Check that `asset_id` matches the folder name exactly
- Verify `manifest.json` is valid JSON
- Check the asset is in the correct category folder

### MuJoCo Load Error

- Ensure MJCF fragment is valid XML
- Check that it doesn't have a `<mujoco>` wrapper
- Verify mesh file paths are correct

### Search Not Finding Asset

- Add more `tags` and `human_names`
- Check spelling in the manifest
- Use `catalog.list_all()` to see all loaded assets

