# Neoscene

Neoscene is a text-to-scene generator for MuJoCo.

## Setup

### Create a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### Install dependencies

```bash
pip install -e .
```

Or for development:

```bash
pip install -e ".[dev]"
```

### Configure API Key (for LLM features)

Create a `.env` file in the project root:

```bash
# .env
GEMINI_API_KEY=your-api-key-here
```

Get your API key at: https://makersuite.google.com/app/apikey

## Usage

### Run a Scene from JSON

```bash
source .venv/bin/activate
python -m neoscene.app.main --scene-json examples/nature_demo.json
```

### Generate MJCF without Viewer

```bash
python -m neoscene.app.main --scene-json examples/orchard_scene.json -o scene.xml --no-viewer
```

### CLI Options

```
--scene-json PATH    Path to a SceneSpec JSON file
--assets-path PATH   Custom assets directory (default: neoscene/assets)
--output, -o PATH    Save generated MJCF XML to this path
--no-viewer          Don't launch the MuJoCo viewer
--help               Show help message
```

## Example Scenes

- `examples/orchard_scene.json` - Simple orchard with tractor and crates
- `examples/nature_demo.json` - Natural terrain with trees, tractor, and birds

## Project Structure

```
neoscene/
├── neoscene/
│   ├── app/          # CLI entry points
│   ├── core/         # Core logic (manifests, schemas, LLM client)
│   ├── exporters/    # MJCF export functionality
│   ├── backends/     # MuJoCo runner
│   └── assets/       # Asset library
├── config/           # Configuration files
├── examples/         # Example scene files
├── docs/             # Documentation
└── tests/            # Test suite
```

## Documentation

- [Architecture](docs/architecture.md) - System design
- [Asset Manifest Spec](docs/asset-manifest-spec.md) - Asset format
- [SceneSpec](docs/scene-spec.md) - Scene JSON schema
# neoscene
