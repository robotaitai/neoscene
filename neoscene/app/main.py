"""Neoscene CLI entry point."""

import argparse
import sys
from pathlib import Path
from typing import Optional


def get_default_assets_path() -> Path:
    """Get the default assets directory path."""
    # Assets are in neoscene/assets relative to the package
    return Path(__file__).parent.parent / "assets"


def run_scene(
    scene_json_path: Path,
    assets_path: Optional[Path] = None,
    output_xml: Optional[Path] = None,
    no_viewer: bool = False,
) -> int:
    """Run a scene from a SceneSpec JSON file.

    Args:
        scene_json_path: Path to the SceneSpec JSON file.
        assets_path: Optional custom assets directory.
        output_xml: Optional path to save the generated MJCF XML.
        no_viewer: If True, don't launch the viewer.

    Returns:
        Exit code (0 for success, non-zero for error).
    """
    # Import here to avoid slow startup for --help
    from neoscene.core.asset_catalog import AssetCatalog
    from neoscene.core.scene_schema import SceneSpec
    from neoscene.exporters.mjcf_exporter import scene_to_mjcf, write_scene_to_file

    # Validate scene JSON path
    if not scene_json_path.exists():
        print(f"Error: Scene file not found: {scene_json_path}", file=sys.stderr)
        return 1

    # Load scene spec
    try:
        json_content = scene_json_path.read_text()
        scene = SceneSpec.model_validate_json(json_content)
        print(f"Loaded scene: {scene.name}")
    except Exception as e:
        print(f"Error: Failed to parse scene JSON: {e}", file=sys.stderr)
        return 1

    # Create asset catalog
    if assets_path is None:
        assets_path = get_default_assets_path()

    if not assets_path.exists():
        print(f"Error: Assets directory not found: {assets_path}", file=sys.stderr)
        return 1

    try:
        catalog = AssetCatalog(assets_path)
        print(f"Loaded {len(catalog)} assets from {assets_path}")
    except Exception as e:
        print(f"Error: Failed to load asset catalog: {e}", file=sys.stderr)
        return 1

    # Generate MJCF
    try:
        mjcf_xml = scene_to_mjcf(scene, catalog)
        print(f"Generated MJCF ({len(mjcf_xml)} bytes)")
    except KeyError as e:
        print(f"Error: Asset not found in catalog: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: Failed to generate MJCF: {e}", file=sys.stderr)
        return 1

    # Save XML if requested
    if output_xml:
        try:
            write_scene_to_file(scene, catalog, output_xml)
            print(f"Saved MJCF to: {output_xml}")
        except Exception as e:
            print(f"Error: Failed to save MJCF: {e}", file=sys.stderr)
            return 1

    # Run simulation
    if not no_viewer:
        try:
            from neoscene.backends.mujoco_runner import run_mjcf_xml

            print("Launching MuJoCo viewer...")
            run_mjcf_xml(mjcf_xml)
        except Exception as e:
            print(f"Error: Failed to run simulation: {e}", file=sys.stderr)
            return 1

    return 0


def run_api(host: str = "0.0.0.0", port: int = 8000, reload: bool = False) -> int:
    """Run the FastAPI server.

    Args:
        host: Host to bind to.
        port: Port to listen on.
        reload: Enable auto-reload for development.

    Returns:
        Exit code.
    """
    try:
        import uvicorn

        print(f"Starting Neoscene API server on http://{host}:{port}")
        print(f"API docs available at http://{host}:{port}/docs")
        uvicorn.run(
            "neoscene.app.api:app",
            host=host,
            port=port,
            reload=reload,
        )
        return 0
    except ImportError:
        print("Error: uvicorn not installed. Run: pip install uvicorn", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: Failed to start API server: {e}", file=sys.stderr)
        return 1


def run_generate(prompt: str, assets_path: Optional[Path] = None, output: Optional[Path] = None) -> int:
    """Generate a scene from a text prompt.

    Args:
        prompt: Natural language scene description.
        assets_path: Optional custom assets directory.
        output: Optional path to save the generated scene JSON.

    Returns:
        Exit code.
    """
    import json

    from neoscene.core.asset_catalog import AssetCatalog
    from neoscene.core.llm_client import GeminiClient
    from neoscene.core.scene_agent import SceneAgent
    from neoscene.exporters.mjcf_exporter import scene_to_mjcf

    if assets_path is None:
        assets_path = get_default_assets_path()

    try:
        catalog = AssetCatalog(assets_path)
        llm = GeminiClient.from_default_config()
        agent = SceneAgent(catalog, llm)

        print(f"Generating scene from: \"{prompt}\"")
        spec = agent.generate_and_repair(prompt)
        print(f"Generated: {spec.name}")

        if output:
            output.write_text(json.dumps(spec.model_dump(), indent=2))
            print(f"Saved to: {output}")
        else:
            print(json.dumps(spec.model_dump(), indent=2))

        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser."""
    parser = argparse.ArgumentParser(
        prog="neoscene",
        description="Neoscene: Text-to-scene generator for MuJoCo",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run a scene from JSON
  python -m neoscene.app.main --scene-json examples/orchard_scene.json

  # Generate MJCF without launching viewer
  python -m neoscene.app.main --scene-json examples/orchard_scene.json --output scene.xml --no-viewer

  # Start the API server
  python -m neoscene.app.main --api

  # Generate a scene from text prompt
  python -m neoscene.app.main --generate "An orchard with a tractor"
""",
    )

    # Mode selection
    mode_group = parser.add_mutually_exclusive_group()

    mode_group.add_argument(
        "--scene-json",
        type=Path,
        help="Path to a SceneSpec JSON file to load and run",
    )

    mode_group.add_argument(
        "--api",
        action="store_true",
        help="Start the FastAPI server",
    )

    mode_group.add_argument(
        "--generate",
        type=str,
        metavar="PROMPT",
        help="Generate a scene from a text prompt",
    )

    # Common options
    parser.add_argument(
        "--assets-path",
        type=Path,
        default=None,
        help="Path to assets directory (default: neoscene/assets)",
    )

    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=None,
        help="Save generated output to this path",
    )

    parser.add_argument(
        "--no-viewer",
        action="store_true",
        help="Don't launch the MuJoCo viewer",
    )

    # API options
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="API server host (default: 0.0.0.0)",
    )

    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="API server port (default: 8000)",
    )

    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for API development",
    )

    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 0.1.0",
    )

    return parser


def main() -> None:
    """Main entry point for the neoscene CLI."""
    parser = create_parser()
    args = parser.parse_args()

    # Determine mode and run
    if args.api:
        exit_code = run_api(host=args.host, port=args.port, reload=args.reload)
    elif args.generate:
        exit_code = run_generate(
            prompt=args.generate,
            assets_path=args.assets_path,
            output=args.output,
        )
    elif args.scene_json:
        exit_code = run_scene(
            scene_json_path=args.scene_json,
            assets_path=args.assets_path,
            output_xml=args.output,
            no_viewer=args.no_viewer,
        )
    else:
        # No mode specified, show help
        print("neoscene CLI - Text-to-scene generator for MuJoCo")
        print()
        print("Usage:")
        print("  python -m neoscene.app.main --scene-json <path>  # Run a scene")
        print("  python -m neoscene.app.main --api                # Start API server")
        print("  python -m neoscene.app.main --generate <prompt>  # Generate from text")
        print()
        print("Run with --help for more options.")
        exit_code = 0

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
