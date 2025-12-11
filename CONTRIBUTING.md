# Contributing to Neoscene

Thank you for your interest in contributing to Neoscene!

## Getting Started

1. **Fork and clone the repository**
   ```bash
   git clone https://github.com/your-username/neoscene.git
   cd neoscene
   ```

2. **Create a virtual environment**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **Install in development mode**
   ```bash
   pip install -e ".[dev]"
   ```

4. **Run tests**
   ```bash
   pytest
   ```

## Development Workflow

1. Create a branch for your feature/fix
   ```bash
   git checkout -b feature/my-feature
   ```

2. Make your changes

3. Run tests and linting
   ```bash
   pytest
   ruff check neoscene/
   ruff format neoscene/
   ```

4. Submit a pull request

## Priority Areas

We especially welcome contributions in these areas:

### 🎨 Assets
- Add new 3D assets with proper manifests
- Improve existing asset MJCF for realism
- Add mesh-based assets

### 🧠 LLM Improvements
- Add support for other LLM providers (OpenAI, Anthropic)
- Improve prompt engineering for better scene generation
- Add function calling / tool use

### 📐 Layouts
- Add new layout types (circle, line, cluster)
- Implement collision detection
- Add constraint-based placement

### 📚 Documentation
- Improve docstrings
- Add tutorials and examples
- Create video demos

## Code Style

- Follow PEP 8
- Use type hints for all public functions
- Add docstrings with Args/Returns/Raises sections
- Keep functions focused and under 50 lines when possible

## Adding Assets

See [docs/adding-assets.md](docs/adding-assets.md) for a complete guide.

Quick checklist:
- [ ] Create folder in appropriate category
- [ ] Add `manifest.json` with all required fields
- [ ] Add MJCF fragment (no `<mujoco>` wrapper)
- [ ] Test that the asset loads correctly
- [ ] Add semantic tags for LLM matching

## Testing

- Write tests for new features
- Use pytest fixtures for common setup
- Mock external dependencies (LLM, MuJoCo viewer)
- Test both happy path and error cases

## Questions?

Open an issue or discussion on GitHub!

