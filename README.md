# Neoscene

**Text-to-scene generator for MuJoCo simulations.**

Neoscene converts natural language descriptions into valid MuJoCo scenes. Describe what you want, and Neoscene uses an LLM to select assets, position objects, and generate simulation-ready MJCF XML.

```
"An orchard with a red tractor and 5 crates" → 🤖 → MuJoCo Scene
```

## Features

- 🗣️ **Natural language input**: Describe scenes in plain English
- 🧠 **LLM-powered**: Uses Gemini to understand and compose scenes
- 📦 **Asset catalog**: Extensible library of environments, robots, and props
- 🎯 **Smart layouts**: Grid and random placement patterns
- 🔌 **REST API**: FastAPI server for integration
- 🎮 **MuJoCo ready**: Direct export to MJCF XML

## Quick Start

### 1. Clone and Install

```bash
git clone https://github.com/your-org/neoscene.git
cd neoscene
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 2. Configure API Key

```bash
echo "GEMINI_API_KEY=your-api-key-here" > .env
```

Get your API key at: https://makersuite.google.com/app/apikey

### 3. Generate Your First Scene

**Option A: CLI with text prompt**
```bash
python -m neoscene.app.main --generate "An orchard with a tractor and some crates"
```

**Option B: Run from JSON file**
```bash
python -m neoscene.app.main --scene-json examples/orchard_scene.json
```

**Option C: API server**
```bash
# Terminal 1: Start server
python -m neoscene.app.main --api

# Terminal 2: Generate scene
curl -X POST http://localhost:8000/generate_scene \
  -H "Content-Type: application/json" \
  -d '{"prompt": "A terrain with trees and a red tractor"}'
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     User Prompt                              │
│              "An orchard with a tractor"                     │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    SceneAgent                                │
│  • Builds prompt with schema + available assets              │
│  • Calls Gemini LLM                                          │
│  • Parses and validates response                             │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    SceneSpec (JSON)                          │
│  • Environment: which base scene to use                      │
│  • Objects: assets with positions/layouts                    │
│  • Cameras: viewpoints for observation                       │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                   MJCF Exporter                              │
│  • Resolves asset references                                 │
│  • Generates grid/random layouts                             │
│  • Produces valid MuJoCo XML                                 │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    MuJoCo Scene                              │
│  • Ready for simulation                                      │
│  • Can be saved to file or viewed directly                   │
└─────────────────────────────────────────────────────────────┘
```

## Project Structure

```
neoscene/
├── neoscene/
│   ├── app/
│   │   ├── main.py          # CLI entry point
│   │   └── api.py           # FastAPI server
│   ├── core/
│   │   ├── asset_catalog.py # Asset discovery and search
│   │   ├── asset_manifest.py # Manifest schema
│   │   ├── scene_schema.py  # SceneSpec schema
│   │   ├── scene_agent.py   # LLM orchestration
│   │   ├── scene_tools.py   # LLM-callable tools
│   │   ├── llm_client.py    # Gemini wrapper
│   │   ├── errors.py        # Custom exceptions
│   │   └── logging_config.py
│   ├── exporters/
│   │   └── mjcf_exporter.py # SceneSpec → MJCF
│   ├── backends/
│   │   └── mujoco_runner.py # MuJoCo simulation
│   └── assets/              # Asset library
│       ├── environments/
│       ├── robots/
│       ├── props/
│       └── sensors/
├── config/
│   ├── llm_config.yaml      # LLM settings
│   └── scene_spec.schema.json
├── examples/                 # Example scenes
├── docs/                     # Documentation
└── tests/                    # Test suite
```

## CLI Reference

```bash
# Run a scene from JSON
python -m neoscene.app.main --scene-json examples/nature_demo.json

# Generate from text prompt
python -m neoscene.app.main --generate "A field with trees"

# Generate and save to file
python -m neoscene.app.main --generate "..." -o scene.json

# Run without viewer
python -m neoscene.app.main --scene-json scene.json --no-viewer -o scene.xml

# Start API server
python -m neoscene.app.main --api --port 8000 --reload
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/assets` | GET | List all assets |
| `/assets?category=robot` | GET | Filter by category |
| `/assets/search` | POST | Search assets by query |
| `/generate_scene` | POST | Generate scene from prompt |
| `/docs` | GET | OpenAPI documentation |

### Generate Scene Request

```json
{
  "prompt": "An orchard with a tractor and crates",
  "include_mjcf": true,
  "repair_on_error": true
}
```

### Generate Scene Response

```json
{
  "id": "uuid",
  "scene_spec": {
    "name": "orchard_scene",
    "environment": {"asset_id": "orchard"},
    "objects": [...],
    "cameras": [...]
  },
  "mjcf_xml": "<mujoco>...</mujoco>",
  "created_at": "2024-..."
}
```

## Adding New Assets

See [docs/adding-assets.md](docs/adding-assets.md) for a complete guide.

Quick summary:

1. Create folder: `neoscene/assets/props/my_asset/`
2. Add MJCF fragment: `mjcf/my_asset.xml`
3. Add manifest: `manifest.json`

```json
{
  "asset_id": "my_asset",
  "name": "My Custom Asset",
  "category": "prop",
  "tags": ["custom"],
  "mjcf_include": "mjcf/my_asset.xml",
  "physical_size": [1.0, 0.5, 0.5]
}
```

## Available Assets

| Category | Assets |
|----------|--------|
| Environments | `orchard`, `terrain` |
| Robots | `tractor_bluewhite`, `tractor_red` |
| Props | `crate_wooden_small`, `trees`, `bird` |
| Sensors | `cam_top_down` |

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `GEMINI_API_KEY` | Google Gemini API key | Required |
| `GOOGLE_API_KEY` | Alternative API key name | - |
| `NEOSCENE_LOG_LEVEL` | Logging level | INFO |

### LLM Config (`config/llm_config.yaml`)

```yaml
default_model: "gemini-2.0-flash"
temperature: 0.3
max_output_tokens: 2048
```

## Development

### Running Tests

```bash
pip install -e ".[dev]"
pytest -v
```

### Code Style

```bash
ruff check neoscene/
ruff format neoscene/
```

## Documentation

- [Architecture](docs/architecture.md) - System design overview
- [SceneSpec Schema](docs/scene-spec.md) - JSON schema reference
- [Asset Manifest Spec](docs/asset-manifest-spec.md) - Asset format
- [Adding Assets](docs/adding-assets.md) - How to add new assets
- [Roadmap](docs/ROADMAP.md) - Planned features

## Examples

- `examples/orchard_scene.json` - Simple farm scene
- `examples/nature_demo.json` - Terrain with trees and birds
- `examples/warehouse_scene.json` - Indoor storage scene
- `examples/curl_generate_scene.sh` - API usage examples

## License

MIT License - see [LICENSE](LICENSE) for details.

## Contributing

Contributions welcome! See the [Roadmap](docs/ROADMAP.md) for priority areas.
