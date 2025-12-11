"""Tests for the AssetCatalog class."""

from pathlib import Path

import pytest

from neoscene.core.asset_catalog import AssetCatalog, AssetSummary
from neoscene.core.asset_manifest import AssetManifest

# Path to assets directory
ASSETS_DIR = Path(__file__).parent.parent / "neoscene" / "assets"


@pytest.fixture
def catalog() -> AssetCatalog:
    """Create an AssetCatalog instance for testing."""
    return AssetCatalog(ASSETS_DIR)


class TestAssetCatalogScanning:
    """Tests for catalog scanning functionality."""

    def test_scan_finds_all_manifests(self, catalog: AssetCatalog) -> None:
        """Verify that scanning finds all known manifests."""
        # We have 4 assets: orchard, tractor_bluewhite, crate_wooden_small, cam_top_down
        assert len(catalog) >= 4

    def test_scan_loads_expected_assets(self, catalog: AssetCatalog) -> None:
        """Verify that specific expected assets are loaded."""
        assert "orchard" in catalog
        assert "tractor_bluewhite" in catalog
        assert "crate_wooden_small" in catalog
        assert "cam_top_down" in catalog

    def test_scan_populates_summaries(self, catalog: AssetCatalog) -> None:
        """Verify that summaries are populated correctly."""
        summaries = catalog.list_all()
        assert len(summaries) >= 4

        # Check that summaries have the expected fields
        for summary in summaries:
            assert isinstance(summary, AssetSummary)
            assert summary.asset_id
            assert summary.name
            assert summary.category in {"environment", "robot", "prop", "sensor"}


class TestAssetCatalogSearch:
    """Tests for catalog search functionality."""

    def test_search_crate_returns_crate_asset(self, catalog: AssetCatalog) -> None:
        """Verify that searching for 'crate' returns the crate asset."""
        results = catalog.search("crate")
        assert len(results) > 0
        assert any(r.asset_id == "crate_wooden_small" for r in results)

    def test_search_tractor_returns_tractor(self, catalog: AssetCatalog) -> None:
        """Verify that searching for 'tractor' returns the tractor asset."""
        results = catalog.search("tractor")
        assert len(results) > 0
        assert any(r.asset_id == "tractor_bluewhite" for r in results)

    def test_search_with_category_filter(self, catalog: AssetCatalog) -> None:
        """Verify that category filter works correctly."""
        # Search for 'tractor' with category='robot'
        results = catalog.search("tractor", category="robot")
        assert len(results) > 0
        assert all(r.category == "robot" for r in results)

    def test_search_with_wrong_category_returns_empty(
        self, catalog: AssetCatalog
    ) -> None:
        """Verify that wrong category returns no results."""
        # Search for 'tractor' with category='prop' should return nothing
        results = catalog.search("tractor", category="prop")
        assert len(results) == 0

    def test_search_respects_limit(self, catalog: AssetCatalog) -> None:
        """Verify that limit parameter is respected."""
        results = catalog.search("a", limit=2)  # 'a' should match multiple assets
        assert len(results) <= 2

    def test_search_by_tag(self, catalog: AssetCatalog) -> None:
        """Verify that search works with tags."""
        results = catalog.search("stackable")
        assert len(results) > 0
        assert any(r.asset_id == "crate_wooden_small" for r in results)

    def test_search_by_semantic_human_name(self, catalog: AssetCatalog) -> None:
        """Verify that search works with semantic human names."""
        results = catalog.search("wooden box")
        assert len(results) > 0
        # Should find the crate since "wooden box" is in human_names
        assert any(r.asset_id == "crate_wooden_small" for r in results)

    def test_search_case_insensitive(self, catalog: AssetCatalog) -> None:
        """Verify that search is case insensitive."""
        results_lower = catalog.search("crate")
        results_upper = catalog.search("CRATE")
        results_mixed = catalog.search("CrAtE")

        assert len(results_lower) == len(results_upper) == len(results_mixed)

    def test_search_no_match_returns_empty(self, catalog: AssetCatalog) -> None:
        """Verify that non-matching query returns empty list."""
        results = catalog.search("xyznonexistent123")
        assert len(results) == 0


class TestAssetCatalogGet:
    """Tests for catalog get functionality."""

    def test_get_returns_correct_manifest(self, catalog: AssetCatalog) -> None:
        """Verify that get() returns the correct manifest."""
        manifest = catalog.get("crate_wooden_small")

        assert isinstance(manifest, AssetManifest)
        assert manifest.asset_id == "crate_wooden_small"
        assert manifest.name == "Small Wooden Crate"
        assert manifest.category == "prop"

    def test_get_nonexistent_raises_error(self, catalog: AssetCatalog) -> None:
        """Verify that get() raises AssetNotFoundError for nonexistent asset."""
        from neoscene.core.errors import AssetNotFoundError

        with pytest.raises(AssetNotFoundError):
            catalog.get("nonexistent_asset_id")

    def test_get_path_returns_correct_path(self, catalog: AssetCatalog) -> None:
        """Verify that get_path() returns the correct folder path."""
        path = catalog.get_path("crate_wooden_small")
        assert path.exists()
        assert path.is_dir()
        assert (path / "manifest.json").exists()


class TestAssetCatalogListAll:
    """Tests for catalog list_all functionality."""

    def test_list_all_returns_all_assets(self, catalog: AssetCatalog) -> None:
        """Verify that list_all() returns all assets."""
        all_assets = catalog.list_all()
        assert len(all_assets) >= 4

    def test_list_all_with_category_filter(self, catalog: AssetCatalog) -> None:
        """Verify that list_all() respects category filter."""
        robots = catalog.list_all(category="robot")
        assert len(robots) >= 1
        assert all(r.category == "robot" for r in robots)

        props = catalog.list_all(category="prop")
        assert len(props) >= 1
        assert all(p.category == "prop" for p in props)


class TestAssetSummary:
    """Tests for AssetSummary model."""

    def test_to_dict_serialization(self, catalog: AssetCatalog) -> None:
        """Verify that to_dict() produces correct output."""
        results = catalog.search("crate")
        assert len(results) > 0

        summary = results[0]
        data = summary.to_dict()

        assert isinstance(data, dict)
        assert "asset_id" in data
        assert "name" in data
        assert "category" in data
        assert "tags" in data
        assert "path" in data
        assert isinstance(data["path"], str)  # Path should be stringified

