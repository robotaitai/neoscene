# Neoscene Architecture

## Overview

Neoscene is a text-to-scene generator for MuJoCo simulations. It converts natural language descriptions into valid MJCF XML by:

1. Using an LLM to interpret the description
2. Selecting assets from a catalog
3. Generating layouts for object placement
4. Exporting a valid MuJoCo scene

## Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                         User Prompt                              │
│              "An orchard with a red tractor and crates"          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                       SceneAgent                                 │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────┐        │
│  │ Asset       │  │   LLM        │  │   Validator     │        │
│  │ Catalog     │──│   (Gemini)   │──│   (Pydantic)    │        │
│  └─────────────┘  └──────────────┘  └─────────────────┘        │
│                                                                  │
│  1. Builds prompt with available assets and schema               │
│  2. Calls LLM to generate SceneSpec JSON                        │
│  3. Validates and repairs if needed                             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                       SceneSpec (IR)                             │
│                                                                  │
│  {                                                               │
│    "name": "orchard_scene",                                      │
│    "environment": {"asset_id": "orchard"},                       │
│    "objects": [                                                  │
│      {"asset_id": "tractor_red", "instances": [...]},           │
│      {"asset_id": "crate_wooden_small", "layout": {...}}        │
│    ],                                                            │
│    "cameras": [...],                                             │
│    "lights": [...]                                               │
│  }                                                               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      MJCF Exporter                               │
│                                                                  │
│  1. Resolves asset references from catalog                       │
│  2. Generates positions from layouts (grid/random)               │
│  3. Inlines asset MJCF fragments                                 │
│  4. Produces valid MuJoCo XML                                    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                       MuJoCo Scene                               │
│                                                                  │
│  <mujoco model="orchard_scene">                                 │
│    <worldbody>                                                   │
│      <body name="env_orchard">...</body>                        │
│      <body name="tractor_red_0">...</body>                      │
│      <body name="crate_0">...</body>                            │
│    </worldbody>                                                  │
│  </mujoco>                                                       │
└─────────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. Asset Catalog (`neoscene/core/asset_catalog.py`)

Manages discovery and search of assets.

```python
catalog = AssetCatalog(Path("neoscene/assets"))
results = catalog.search("tractor")  # Find matching assets
manifest = catalog.get("tractor_red")  # Get full manifest
path = catalog.get_path("tractor_red")  # Get asset folder path
```

**Key features:**
- Scans `assets/` directory for `manifest.json` files
- Provides text-based search across names, tags, semantics
- Returns AssetManifest objects with full metadata

### 2. Scene Schema (`neoscene/core/scene_schema.py`)

Defines the intermediate representation (IR) as Pydantic models.

```python
SceneSpec(
    name="demo",
    environment=EnvironmentSpec(asset_id="orchard"),
    objects=[
        ObjectSpec(
            asset_id="crate_wooden_small",
            layout=GridLayout(origin=[0,0,0], rows=2, cols=3, spacing=[1,1])
        )
    ],
    cameras=[CameraSpec(name="cam", pose=Pose(position=[0,0,5]))]
)
```

**Key models:**
- `SceneSpec`: Top-level scene description
- `ObjectSpec`: Object placement with layout or instances
- `GridLayout` / `RandomLayout`: Layout patterns
- `CameraSpec`, `LightSpec`: Scene configuration

### 3. Scene Agent (`neoscene/core/scene_agent.py`)

Orchestrates LLM-based scene generation.

```python
agent = SceneAgent(catalog, llm_client)
spec = agent.generate_scene_spec("An orchard with trees")
spec = agent.generate_and_repair(prompt)  # With auto-repair
```

**Key features:**
- Builds prompts with asset catalog and schema info
- Parses and validates LLM output
- Provides auto-repair for invalid outputs

### 4. MJCF Exporter (`neoscene/exporters/mjcf_exporter.py`)

Converts SceneSpec to MuJoCo XML.

```python
xml = scene_to_mjcf(scene_spec, catalog)
write_scene_to_file(scene_spec, catalog, Path("scene.xml"))
```

**Key features:**
- Resolves layout patterns to explicit positions
- Inlines asset MJCF fragments
- Handles cameras, lights, physics settings

### 5. LLM Client (`neoscene/core/llm_client.py`)

Wrapper for Gemini API.

```python
llm = GeminiClient.from_default_config()  # Reads .env and config/
response = llm.generate(prompt)
```

**Key features:**
- API key management via `.env` or environment
- Configurable via `config/llm_config.yaml`
- Graceful fallback when API unavailable

## Directory Structure

```
neoscene/
├── neoscene/
│   ├── app/
│   │   ├── main.py          # CLI entry point
│   │   └── api.py           # FastAPI server
│   ├── core/
│   │   ├── asset_catalog.py # Asset discovery and search
│   │   ├── asset_manifest.py # Manifest schema
│   │   ├── scene_schema.py  # SceneSpec IR
│   │   ├── scene_agent.py   # LLM orchestration
│   │   ├── scene_tools.py   # LLM-callable tools
│   │   ├── llm_client.py    # Gemini wrapper
│   │   ├── errors.py        # Custom exceptions
│   │   └── logging_config.py
│   ├── exporters/
│   │   └── mjcf_exporter.py # SceneSpec → MJCF
│   ├── backends/
│   │   └── mujoco_runner.py # MuJoCo viewer
│   └── assets/              # Asset library
│       ├── environments/    # Base scenes
│       ├── robots/          # Vehicles, arms
│       ├── props/           # Crates, trees
│       └── sensors/         # Cameras
├── config/
│   └── llm_config.yaml      # LLM settings
├── examples/                 # Example scenes
├── docs/                     # Documentation
└── tests/                    # Test suite
```

## Asset System

Assets are self-contained packages with:

```
assets/props/crate_wooden_small/
├── manifest.json     # Metadata and semantics
├── mjcf/
│   └── crate.xml     # MJCF geometry fragment
├── meshes/           # (Optional) 3D models
└── textures/         # (Optional) Texture files
```

The manifest provides:
- **Identity**: `asset_id`, `name`, `category`
- **Semantics**: `tags`, `human_names` for LLM matching
- **Physical**: `physical_size` for layout calculations
- **Rules**: `placement_rules` for validation

See [Asset Manifest Spec](asset-manifest-spec.md) for details.

## Entry Points

### CLI

```bash
# Run from JSON
python -m neoscene.app.main --scene-json examples/orchard_scene.json

# Generate from text
python -m neoscene.app.main --generate "An orchard with trees"

# Start API
python -m neoscene.app.main --api
```

### API

```bash
# Generate scene
curl -X POST http://localhost:8000/generate_scene \
  -H "Content-Type: application/json" \
  -d '{"prompt": "An orchard with a tractor"}'

# List assets
curl http://localhost:8000/assets

# Search assets
curl -X POST http://localhost:8000/assets/search \
  -d '{"query": "tractor"}'
```

## Error Handling

All errors inherit from `NeosceneError`:

| Exception | When | HTTP Status |
|-----------|------|-------------|
| `AssetNotFoundError` | Asset ID not in catalog | 404 |
| `SceneValidationError` | Invalid SceneSpec JSON | 400 |
| `LLMError` | Gemini API failure | 502 |
| `LayoutError` | Layout generation fails | 400 |
| `MJCFExportError` | MJCF generation fails | 400 |
| `ConfigurationError` | Missing API key, etc. | 500 |

## Extension Points

### Adding Assets

1. Create folder in appropriate category
2. Add `manifest.json` with metadata
3. Add MJCF fragment in `mjcf/` folder

See [Adding Assets](adding-assets.md) guide.

### Adding LLM Providers

1. Create new client in `neoscene/core/`
2. Implement `generate(prompt) -> str` interface
3. Update `SceneAgent` to accept the new client

### Adding Export Formats

1. Create new exporter in `neoscene/exporters/`
2. Accept `SceneSpec` and `AssetCatalog`
3. Add CLI flag or API endpoint

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=neoscene

# Run specific test file
pytest tests/test_scene_agent.py -v
```
