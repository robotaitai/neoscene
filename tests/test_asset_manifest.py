"""Tests for asset manifest loading and validation."""

from pathlib import Path

import pytest

from neoscene.core.asset_manifest import (
    AssetManifest,
    discover_manifests,
    load_manifest,
)

# Path to assets directory
ASSETS_DIR = Path(__file__).parent.parent / "neoscene" / "assets"

# Valid categories
VALID_CATEGORIES = {"environment", "robot", "prop", "sensor"}


@pytest.fixture
def manifest_paths() -> list[Path]:
    """Discover all manifest files in the assets directory."""
    return discover_manifests(ASSETS_DIR)


def test_manifests_exist(manifest_paths: list[Path]) -> None:
    """Verify that at least some manifests exist."""
    assert len(manifest_paths) >= 3, f"Expected at least 3 manifests, found {len(manifest_paths)}"


def test_all_manifests_load_successfully(manifest_paths: list[Path]) -> None:
    """Verify that all manifest.json files can be loaded without errors."""
    for path in manifest_paths:
        manifest = load_manifest(path)
        assert isinstance(manifest, AssetManifest)


def test_categories_are_valid(manifest_paths: list[Path]) -> None:
    """Verify that all manifests have valid category values."""
    for path in manifest_paths:
        manifest = load_manifest(path)
        assert manifest.category in VALID_CATEGORIES, (
            f"Invalid category '{manifest.category}' in {path}"
        )


def test_asset_ids_are_non_empty(manifest_paths: list[Path]) -> None:
    """Verify that all manifests have non-empty asset_id."""
    for path in manifest_paths:
        manifest = load_manifest(path)
        assert manifest.asset_id, f"Empty asset_id in {path}"
        assert len(manifest.asset_id) > 0


def test_asset_id_matches_folder_name(manifest_paths: list[Path]) -> None:
    """Verify that asset_id matches the containing folder name."""
    for path in manifest_paths:
        manifest = load_manifest(path)
        folder_name = path.parent.name
        assert manifest.asset_id == folder_name, (
            f"asset_id '{manifest.asset_id}' doesn't match folder '{folder_name}'"
        )


def test_mjcf_include_paths_exist(manifest_paths: list[Path]) -> None:
    """Verify that referenced MJCF files exist."""
    for path in manifest_paths:
        manifest = load_manifest(path)
        mjcf_path = path.parent / manifest.mjcf_include
        assert mjcf_path.exists(), f"MJCF file not found: {mjcf_path}"


def test_physical_size_format(manifest_paths: list[Path]) -> None:
    """Verify that physical_size, if set, has exactly 3 dimensions."""
    for path in manifest_paths:
        manifest = load_manifest(path)
        if manifest.physical_size is not None:
            assert len(manifest.physical_size) == 3, (
                f"physical_size should have 3 dimensions in {path}"
            )
            assert all(s > 0 for s in manifest.physical_size), (
                f"physical_size values should be positive in {path}"
            )


def test_specific_manifest_orchard() -> None:
    """Test the orchard environment manifest specifically."""
    path = ASSETS_DIR / "environments" / "orchard" / "manifest.json"
    manifest = load_manifest(path)

    assert manifest.asset_id == "orchard"
    assert manifest.category == "environment"
    assert "outdoor" in manifest.tags
    assert manifest.physical_size is not None


def test_specific_manifest_tractor() -> None:
    """Test the tractor robot manifest specifically."""
    path = ASSETS_DIR / "robots" / "tractor_bluewhite" / "manifest.json"
    manifest = load_manifest(path)

    assert manifest.asset_id == "tractor_bluewhite"
    assert manifest.category == "robot"
    assert "vehicle" in manifest.tags
    assert "ground" in manifest.placement_rules.allow_on


def test_specific_manifest_crate() -> None:
    """Test the wooden crate prop manifest specifically."""
    path = ASSETS_DIR / "props" / "crate_wooden_small" / "manifest.json"
    manifest = load_manifest(path)

    assert manifest.asset_id == "crate_wooden_small"
    assert manifest.category == "prop"
    assert "stackable" in manifest.tags
    assert manifest.placement_rules.min_clearance == 0.02


def test_specific_manifest_camera() -> None:
    """Test the top-down camera sensor manifest specifically."""
    path = ASSETS_DIR / "sensors" / "cam_top_down" / "manifest.json"
    manifest = load_manifest(path)

    assert manifest.asset_id == "cam_top_down"
    assert manifest.category == "sensor"
    assert "camera" in manifest.tags
    assert manifest.physical_size is None  # Cameras don't have physical size

