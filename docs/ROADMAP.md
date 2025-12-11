# Neoscene Roadmap

This document outlines planned features and improvements for Neoscene.

## Current Status (v0.1.0)

✅ Core pipeline: Text → SceneSpec → MJCF → MuJoCo
✅ Asset catalog with manifest-based discovery
✅ Grid and random layout support
✅ FastAPI HTTP interface
✅ Gemini LLM integration
✅ Basic error handling and logging

## Short-term (v0.2.0)

### Asset System
- [ ] **Vector search for assets**: Use embeddings for semantic asset matching
- [ ] **Asset thumbnails**: Generate preview images for assets
- [ ] **Asset validation CLI**: Validate manifests and MJCF files
- [ ] **More asset types**: Support for articulated robots, deformable objects

### Scene Generation
- [ ] **Collision pre-checks**: Detect and prevent object overlaps before export
- [ ] **Scene templates**: Pre-built scene structures (warehouse, outdoor, etc.)
- [ ] **Modify existing scenes**: API to edit and refine generated scenes
- [ ] **Multi-turn conversation**: Iterative scene refinement with context

### Export & Visualization
- [ ] **Offline rendering**: Generate images/videos without GUI
- [ ] **USD export**: Export scenes to Universal Scene Description format
- [ ] **Scene preview API**: Return rendered preview image with scene

## Medium-term (v0.3.0)

### Advanced Layouts
- [ ] **Constraint-based placement**: Define spatial relationships (on, near, inside)
- [ ] **Physics-aware layouts**: Use physics simulation to settle objects
- [ ] **Path planning integration**: Place objects considering navigation

### LLM Improvements
- [ ] **Multi-provider support**: OpenAI, Anthropic, local models
- [ ] **Function calling**: Use native tool/function calling APIs
- [ ] **Streaming responses**: Stream scene generation progress
- [ ] **Cost tracking**: Monitor and limit API usage

### Performance
- [ ] **Caching**: Cache LLM responses and MJCF generation
- [ ] **Async generation**: Non-blocking scene generation
- [ ] **Batch generation**: Generate multiple scenes efficiently

## Long-term (v1.0.0)

### Ecosystem
- [ ] **Asset marketplace**: Community-contributed assets
- [ ] **Web UI**: Browser-based scene editor
- [ ] **Blender integration**: Import/export with Blender
- [ ] **ROS integration**: Publish scenes to ROS topics

### Advanced Features
- [ ] **Procedural assets**: Generate meshes from descriptions
- [ ] **Behavior scripting**: Add agent behaviors to scenes
- [ ] **Multi-robot scenarios**: Complex multi-agent setups
- [ ] **Domain randomization**: Automated variation for training

## Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

Priority areas:
1. Adding new assets with proper manifests
2. Improving layout algorithms
3. Testing with different LLM providers
4. Documentation and examples

## Technical Debt

- [ ] Improve test coverage for edge cases
- [ ] Add integration tests with real MuJoCo
- [ ] Profile and optimize MJCF generation
- [ ] Add type stubs for external dependencies

