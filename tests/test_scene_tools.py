"""Tests for the scene tools module."""

from pathlib import Path

import pytest

from neoscene.core.asset_catalog import AssetCatalog
from neoscene.core.scene_tools import (
    get_asset_details,
    grid_layout_to_dict,
    list_assets_by_category,
    manifest_to_dict,
    random_layout_to_dict,
    search_assets,
    suggest_grid_layout,
    suggest_layout_for_count,
    suggest_random_layout,
)

# Path to assets directory
ASSETS_DIR = Path(__file__).parent.parent / "neoscene" / "assets"


@pytest.fixture
def catalog() -> AssetCatalog:
    """Create an AssetCatalog instance for testing."""
    return AssetCatalog(ASSETS_DIR)


class TestSearchAssets:
    """Tests for the search_assets function."""

    def test_search_finds_crate(self, catalog: AssetCatalog) -> None:
        """Test that searching for 'crate' returns the wooden crate."""
        results = search_assets(catalog, "crate")

        assert len(results) > 0
        assert any(r["asset_id"] == "crate_wooden_small" for r in results)

    def test_search_returns_dicts(self, catalog: AssetCatalog) -> None:
        """Test that results are plain dictionaries."""
        results = search_assets(catalog, "tractor")

        assert len(results) > 0
        assert isinstance(results[0], dict)
        assert "asset_id" in results[0]
        assert "name" in results[0]
        assert "category" in results[0]
        assert "tags" in results[0]

    def test_search_with_category_filter(self, catalog: AssetCatalog) -> None:
        """Test category filtering works."""
        results = search_assets(catalog, "tractor", category="robot")

        assert len(results) > 0
        assert all(r["category"] == "robot" for r in results)

    def test_search_respects_limit(self, catalog: AssetCatalog) -> None:
        """Test that limit parameter is respected."""
        results = search_assets(catalog, "a", limit=2)

        assert len(results) <= 2

    def test_search_no_results(self, catalog: AssetCatalog) -> None:
        """Test that non-matching query returns empty list."""
        results = search_assets(catalog, "xyznonexistent123")

        assert results == []

    def test_search_finds_trees(self, catalog: AssetCatalog) -> None:
        """Test searching for trees."""
        results = search_assets(catalog, "tree", category="prop")

        assert len(results) > 0
        assert any(r["asset_id"] == "trees" for r in results)


class TestGetAssetDetails:
    """Tests for the get_asset_details function."""

    def test_get_crate_details(self, catalog: AssetCatalog) -> None:
        """Test getting details for the wooden crate."""
        details = get_asset_details(catalog, "crate_wooden_small")

        assert details["asset_id"] == "crate_wooden_small"
        assert details["name"] == "Small Wooden Crate"
        assert details["category"] == "prop"
        assert details["physical_size"] == [0.6, 0.4, 0.4]
        assert "placement_rules" in details
        assert "semantics" in details

    def test_get_nonexistent_asset_raises(self, catalog: AssetCatalog) -> None:
        """Test that nonexistent asset raises AssetNotFoundError."""
        from neoscene.core.errors import AssetNotFoundError

        with pytest.raises(AssetNotFoundError):
            get_asset_details(catalog, "nonexistent_asset")

    def test_details_are_serializable(self, catalog: AssetCatalog) -> None:
        """Test that details can be serialized to JSON."""
        import json

        details = get_asset_details(catalog, "tractor_red")
        # Should not raise
        json_str = json.dumps(details)
        assert json_str is not None


class TestListAssetsByCategory:
    """Tests for the list_assets_by_category function."""

    def test_list_all_assets(self, catalog: AssetCatalog) -> None:
        """Test listing all assets."""
        results = list_assets_by_category(catalog)

        assert len(results) >= 4
        assert isinstance(results[0], dict)

    def test_list_robots(self, catalog: AssetCatalog) -> None:
        """Test listing only robots."""
        results = list_assets_by_category(catalog, category="robot")

        assert len(results) >= 1
        assert all(r["category"] == "robot" for r in results)

    def test_list_environments(self, catalog: AssetCatalog) -> None:
        """Test listing only environments."""
        results = list_assets_by_category(catalog, category="environment")

        assert len(results) >= 1
        assert all(r["category"] == "environment" for r in results)


class TestSuggestGridLayout:
    """Tests for the suggest_grid_layout function."""

    def test_grid_layout_basic(self) -> None:
        """Test basic grid layout generation."""
        layout = suggest_grid_layout(
            count=6,
            origin=[0.0, 0.0, 0.0],
            max_per_row=3,
        )

        assert layout["type"] == "grid"
        assert layout["rows"] == 2
        assert layout["cols"] == 3
        assert layout["origin"] == [0.0, 0.0, 0.0]

    def test_grid_layout_5_items_3_per_row(self) -> None:
        """Test grid layout with 5 items, max 3 per row."""
        layout = suggest_grid_layout(
            count=5,
            origin=[0.0, 0.0, 0.0],
            max_per_row=3,
        )

        # 5 items, 3 per row = 2 rows needed (3 + 2)
        assert layout["rows"] == 2
        assert layout["cols"] == 3
        # Total capacity is 6, which covers 5
        assert layout["rows"] * layout["cols"] >= 5

    def test_grid_layout_custom_spacing(self) -> None:
        """Test grid layout with custom spacing."""
        layout = suggest_grid_layout(
            count=4,
            origin=[1.0, 2.0, 0.0],
            max_per_row=2,
            spacing_xy=[1.5, 2.0],
        )

        assert layout["spacing"] == [1.5, 2.0]
        assert layout["origin"] == [1.0, 2.0, 0.0]

    def test_grid_layout_single_item(self) -> None:
        """Test grid layout with a single item."""
        layout = suggest_grid_layout(count=1, origin=[0.0, 0.0, 0.0])

        assert layout["rows"] == 1
        assert layout["cols"] == 1

    def test_grid_layout_with_yaw_variation(self) -> None:
        """Test grid layout with yaw variation."""
        layout = suggest_grid_layout(
            count=4,
            origin=[0.0, 0.0, 0.0],
            yaw_variation_deg=15.0,
        )

        assert layout["yaw_variation_deg"] == 15.0

    def test_grid_layout_more_items_than_per_row(self) -> None:
        """Test that items exceeding max_per_row create more rows."""
        layout = suggest_grid_layout(
            count=10,
            origin=[0.0, 0.0, 0.0],
            max_per_row=4,
        )

        assert layout["cols"] == 4
        assert layout["rows"] == 3  # ceil(10/4) = 3


class TestSuggestRandomLayout:
    """Tests for the suggest_random_layout function."""

    def test_random_layout_basic(self) -> None:
        """Test basic random layout generation."""
        layout = suggest_random_layout(
            count=10,
            center=[5.0, 5.0, 0.0],
            radius=3.0,
        )

        assert layout["type"] == "random"
        assert layout["count"] == 10
        assert layout["center"] == [5.0, 5.0, 0.0]
        assert layout["radius"] == 3.0

    def test_random_layout_min_separation(self) -> None:
        """Test random layout with min separation."""
        layout = suggest_random_layout(
            count=5,
            center=[0.0, 0.0, 0.0],
            radius=10.0,
            min_separation=2.0,
        )

        assert layout["min_separation"] == 2.0

    def test_random_layout_no_random_yaw(self) -> None:
        """Test random layout without random yaw."""
        layout = suggest_random_layout(
            count=5,
            center=[0.0, 0.0, 0.0],
            radius=5.0,
            random_yaw=False,
        )

        assert layout["random_yaw"] is False


class TestSuggestLayoutForCount:
    """Tests for the suggest_layout_for_count function."""

    def test_organized_layout_uses_grid(self) -> None:
        """Test that organized layout prefers grid."""
        layout = suggest_layout_for_count(
            count=4,
            center=[0.0, 0.0, 0.0],
            organized=True,
        )

        assert layout["type"] == "grid"

    def test_unorganized_layout_uses_random(self) -> None:
        """Test that unorganized layout uses random."""
        layout = suggest_layout_for_count(
            count=10,
            center=[0.0, 0.0, 0.0],
            organized=False,
        )

        assert layout["type"] == "random"

    def test_layout_respects_area_size(self) -> None:
        """Test that area_size affects the layout."""
        layout = suggest_layout_for_count(
            count=4,
            center=[0.0, 0.0, 0.0],
            area_size=20.0,
            organized=False,
        )

        assert layout["radius"] == 10.0  # area_size / 2


class TestSerializationHelpers:
    """Tests for the serialization helper functions."""

    def test_manifest_to_dict(self, catalog: AssetCatalog) -> None:
        """Test manifest serialization."""
        manifest = catalog.get("crate_wooden_small")
        data = manifest_to_dict(manifest)

        assert isinstance(data, dict)
        assert data["asset_id"] == "crate_wooden_small"
        assert isinstance(data["tags"], list)
        assert isinstance(data["placement_rules"], dict)
        assert isinstance(data["semantics"], dict)

    def test_grid_layout_to_dict(self) -> None:
        """Test grid layout serialization."""
        from neoscene.core.scene_schema import GridLayout

        layout = GridLayout(
            origin=[1.0, 2.0, 3.0],
            rows=2,
            cols=3,
            spacing=[0.5, 0.6],
        )
        data = grid_layout_to_dict(layout)

        assert data["type"] == "grid"
        assert data["rows"] == 2
        assert data["cols"] == 3

    def test_random_layout_to_dict(self) -> None:
        """Test random layout serialization."""
        from neoscene.core.scene_schema import RandomLayout

        layout = RandomLayout(
            center=[0.0, 0.0, 0.0],
            radius=5.0,
            count=10,
        )
        data = random_layout_to_dict(layout)

        assert data["type"] == "random"
        assert data["count"] == 10
        assert data["radius"] == 5.0

