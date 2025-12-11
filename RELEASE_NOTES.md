# Neoscene v0.1.0 Release Notes

**Release Date:** December 11, 2024

## What is Neoscene?

Neoscene is a **text-to-scene generator for MuJoCo simulations**. You describe a scene in natural language, and Neoscene uses an LLM (Gemini) to:

1. Select appropriate assets from a catalog
2. Position objects in 3D space
3. Generate valid MuJoCo MJCF XML
4. Launch an interactive viewer

## How to Use

### Option 1: Chat UI (Recommended)

```bash
# Start the server
cd neoscene
source .venv/bin/activate
uvicorn neoscene.app.api:app --reload

# Open browser to http://localhost:8000/
```

Then type scene descriptions like:
- "A terrain with a red tractor and 5 trees scattered around"
- "An orchard with wooden crates in a 3x3 grid"
- "A field with birds flying overhead"

The MuJoCo viewer opens automatically with your scene.

### Option 2: CLI

```bash
# From JSON file
python -m neoscene.app.main --scene-json examples/orchard_scene.json

# From text prompt
python -m neoscene.app.main --generate "An orchard with a tractor"

# Save MJCF without viewer
python -m neoscene.app.main --scene-json examples/nature_demo.json -o scene.xml --no-viewer
```

### Option 3: REST API

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "A terrain with trees and a tractor"}'
```

## Features in v0.1.0

### Core Pipeline
- ✅ Natural language → SceneSpec (IR) → MJCF XML → MuJoCo
- ✅ Asset catalog with manifest-based discovery
- ✅ Grid and random layout patterns
- ✅ Gemini LLM integration with auto-repair

### Assets Included
| Category | Assets |
|----------|--------|
| Environments | `orchard`, `terrain` |
| Robots | `tractor_bluewhite`, `tractor_red` |
| Props | `crate_wooden_small`, `trees`, `bird` |
| Sensors | `cam_top_down` |

### API Endpoints
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Chat web UI |
| `/chat` | POST | Chat-driven scene generation |
| `/generate_scene` | POST | One-shot scene generation |
| `/assets` | GET | List all assets |
| `/assets/search` | POST | Search assets |
| `/health` | GET | Health check |
| `/docs` | GET | OpenAPI documentation |

### Chat UI Features
- Two-column layout (chat left, scene status right)
- Session persistence across messages
- Real-time scene updates
- MuJoCo viewer auto-launch

## Project Structure

```
neoscene/
├── neoscene/
│   ├── app/
│   │   ├── api.py           # FastAPI server
│   │   ├── main.py          # CLI entry point
│   │   └── static/          # Chat UI (HTML/JS/CSS)
│   ├── core/
│   │   ├── asset_catalog.py # Asset discovery
│   │   ├── scene_agent.py   # LLM orchestration
│   │   ├── scene_schema.py  # SceneSpec IR
│   │   └── llm_client.py    # Gemini wrapper
│   ├── exporters/
│   │   └── mjcf_exporter.py # SceneSpec → MJCF
│   ├── backends/
│   │   ├── mujoco_runner.py # MuJoCo viewer
│   │   └── session_manager.py # Chat sessions
│   └── assets/              # Asset library
├── examples/                # Example scenes
├── docs/                    # Documentation
└── tests/                   # Test suite (188 tests)
```

## Configuration

1. Create `.env` file:
   ```
   GEMINI_API_KEY=your-api-key-here
   ```

2. Get API key at: https://makersuite.google.com/app/apikey

## Requirements

- Python 3.10+
- MuJoCo
- Gemini API key

## Installation

```bash
git clone https://github.com/robotaitai/neoscene.git
cd neoscene
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Known Limitations

- Each chat message creates a new scene (no incremental editing yet)
- Assets use primitive geometries (mesh support coming)
- No collision detection during layout generation

## Roadmap

See [docs/ROADMAP.md](docs/ROADMAP.md) for planned features:
- Vector search for assets
- Collision pre-checks
- Scene templates
- Offline rendering
- Multi-provider LLM support

## License

MIT License

