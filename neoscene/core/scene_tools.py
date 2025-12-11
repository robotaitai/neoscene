"""LLM-facing tools for scene generation.

This module provides functions that the LLM agent can call to search for assets
and suggest layouts. These are designed to be easily described in system prompts
and return JSON-serializable data.

Tools:
    - search_assets: Find assets matching a natural language query
    - suggest_grid_layout: Create a grid layout for multiple objects
    - suggest_random_layout: Create a random scatter layout
    - get_asset_details: Get full details about a specific asset
"""

import math
from typing import Any, Dict, List, Literal, Optional

from neoscene.core.asset_catalog import AssetCatalog, AssetSummary
from neoscene.core.asset_manifest import AssetManifest
from neoscene.core.scene_schema import GridLayout, RandomLayout


# =============================================================================
# Asset Search Tools
# =============================================================================


def search_assets(
    catalog: AssetCatalog,
    query: str,
    category: Optional[Literal["environment", "robot", "prop", "sensor"]] = None,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """Search for assets matching a natural language query.

    Use this tool to find assets that match user descriptions. The search looks
    at asset names, tags, and semantic information (human_names, usage).

    Args:
        catalog: The asset catalog to search in.
        query: Natural language search query (e.g., "wooden box", "farm vehicle").
        category: Optional filter by category:
            - "environment": Base scenes (terrains, rooms)
            - "robot": Controllable agents (vehicles, arms)
            - "prop": Static objects (crates, trees)
            - "sensor": Cameras and sensors
        limit: Maximum number of results to return.

    Returns:
        List of asset summaries as dictionaries with keys:
            - asset_id: Unique identifier for the asset
            - name: Human-readable name
            - category: Asset category
            - tags: List of descriptive tags
            - path: Path to the asset folder

    Example:
        >>> results = search_assets(catalog, "tractor", category="robot")
        >>> results[0]
        {'asset_id': 'tractor_red', 'name': 'Red Farm Tractor', ...}
    """
    summaries = catalog.search(query, category=category, limit=limit)
    return [summary.to_dict() for summary in summaries]


def get_asset_details(
    catalog: AssetCatalog,
    asset_id: str,
) -> Dict[str, Any]:
    """Get full details about a specific asset.

    Use this tool to get complete information about an asset after finding
    it with search_assets. Returns all manifest data including physical size
    and placement rules.

    Args:
        catalog: The asset catalog.
        asset_id: The unique asset identifier.

    Returns:
        Full asset manifest as a dictionary with keys:
            - asset_id, name, category, tags
            - mjcf_include: Path to the MJCF file
            - physical_size: [x, y, z] dimensions in meters (or null)
            - placement_rules: {allow_on: [...], min_clearance: float}
            - semantics: {human_names: [...], usage: [...]}

    Raises:
        KeyError: If the asset_id is not found.

    Example:
        >>> details = get_asset_details(catalog, "crate_wooden_small")
        >>> details["physical_size"]
        [0.6, 0.4, 0.4]
    """
    manifest = catalog.get(asset_id)
    return manifest_to_dict(manifest)


def list_assets_by_category(
    catalog: AssetCatalog,
    category: Optional[Literal["environment", "robot", "prop", "sensor"]] = None,
) -> List[Dict[str, Any]]:
    """List all available assets, optionally filtered by category.

    Use this tool to see what assets are available in the catalog.

    Args:
        catalog: The asset catalog.
        category: Optional category filter.

    Returns:
        List of asset summaries as dictionaries.

    Example:
        >>> environments = list_assets_by_category(catalog, "environment")
        >>> [e["asset_id"] for e in environments]
        ['orchard', 'terrain']
    """
    summaries = catalog.list_all(category=category)
    return [summary.to_dict() for summary in summaries]


# =============================================================================
# Layout Suggestion Tools
# =============================================================================


def suggest_grid_layout(
    count: int,
    origin: List[float],
    max_per_row: int = 5,
    spacing_xy: Optional[List[float]] = None,
    yaw_variation_deg: float = 0.0,
) -> Dict[str, Any]:
    """Suggest a grid layout for placing multiple objects.

    Use this tool when you need to arrange multiple instances of an object
    in an organized grid pattern (e.g., rows of crates, parking lot).

    Args:
        count: Total number of objects to place.
        origin: Starting position [x, y, z] of the grid.
        max_per_row: Maximum objects per row (columns).
        spacing_xy: Distance between objects [dx, dy] in meters.
                   Defaults to [1.0, 1.0] if not specified.
        yaw_variation_deg: Random rotation variation in degrees.

    Returns:
        GridLayout as a dictionary with keys:
            - type: "grid"
            - origin: [x, y, z] starting position
            - rows: Number of rows
            - cols: Number of columns
            - spacing: [dx, dy] spacing
            - yaw_variation_deg: Rotation variation

    Example:
        >>> layout = suggest_grid_layout(count=6, origin=[0, 0, 0], max_per_row=3)
        >>> layout
        {'type': 'grid', 'origin': [0, 0, 0], 'rows': 2, 'cols': 3, 'spacing': [1.0, 1.0], ...}
    """
    if spacing_xy is None:
        spacing_xy = [1.0, 1.0]

    # Calculate rows and columns
    cols = min(count, max_per_row)
    rows = math.ceil(count / cols)

    layout = GridLayout(
        origin=origin,
        rows=rows,
        cols=cols,
        spacing=spacing_xy,
        yaw_variation_deg=yaw_variation_deg,
    )

    return grid_layout_to_dict(layout)


def suggest_random_layout(
    count: int,
    center: List[float],
    radius: float,
    min_separation: float = 0.5,
    random_yaw: bool = True,
) -> Dict[str, Any]:
    """Suggest a random scatter layout for placing objects.

    Use this tool when you need to place objects in a natural, random pattern
    (e.g., trees in a forest, rocks on terrain, scattered debris).

    Args:
        count: Number of objects to place.
        center: Center point [x, y, z] of the spawn area.
        radius: Radius of the circular spawn area in meters.
        min_separation: Minimum distance between objects in meters.
        random_yaw: Whether to randomize object orientation.

    Returns:
        RandomLayout as a dictionary with keys:
            - type: "random"
            - center: [x, y, z] center point
            - radius: Spawn area radius
            - count: Number of objects
            - min_separation: Minimum distance between objects
            - random_yaw: Whether to randomize orientation

    Example:
        >>> layout = suggest_random_layout(count=10, center=[0, 0, 0], radius=5.0)
        >>> layout
        {'type': 'random', 'center': [0, 0, 0], 'radius': 5.0, 'count': 10, ...}
    """
    layout = RandomLayout(
        center=center,
        radius=radius,
        count=count,
        min_separation=min_separation,
        random_yaw=random_yaw,
    )

    return random_layout_to_dict(layout)


def suggest_layout_for_count(
    count: int,
    center: List[float],
    area_size: float = 10.0,
    organized: bool = True,
) -> Dict[str, Any]:
    """Automatically suggest an appropriate layout based on object count.

    Use this tool when you're not sure whether to use a grid or random layout.
    It will choose based on the count and whether organization is desired.

    Args:
        count: Number of objects to place.
        center: Center point [x, y, z] of the placement area.
        area_size: Size of the area in meters.
        organized: If True, prefer grid layout; if False, prefer random.

    Returns:
        Either a GridLayout or RandomLayout as a dictionary.

    Example:
        >>> layout = suggest_layout_for_count(4, center=[0, 0, 0], organized=True)
        >>> layout["type"]
        'grid'
    """
    if organized and count <= 20:
        # Use grid for organized placement
        spacing = area_size / max(math.ceil(math.sqrt(count)), 2)
        origin = [
            center[0] - area_size / 2,
            center[1] - area_size / 2,
            center[2],
        ]
        return suggest_grid_layout(
            count=count,
            origin=origin,
            max_per_row=math.ceil(math.sqrt(count)),
            spacing_xy=[spacing, spacing],
        )
    else:
        # Use random for natural placement
        return suggest_random_layout(
            count=count,
            center=center,
            radius=area_size / 2,
            min_separation=area_size / (count + 1) * 0.8,
        )


# =============================================================================
# Serialization Helpers
# =============================================================================


def manifest_to_dict(manifest: AssetManifest) -> Dict[str, Any]:
    """Convert an AssetManifest to a JSON-serializable dictionary.

    Args:
        manifest: The manifest to convert.

    Returns:
        Dictionary representation of the manifest.
    """
    return {
        "asset_id": manifest.asset_id,
        "name": manifest.name,
        "category": manifest.category,
        "tags": manifest.tags,
        "mjcf_include": manifest.mjcf_include,
        "physical_size": manifest.physical_size,
        "placement_rules": {
            "allow_on": manifest.placement_rules.allow_on,
            "min_clearance": manifest.placement_rules.min_clearance,
        },
        "semantics": {
            "human_names": manifest.semantics.human_names,
            "usage": manifest.semantics.usage,
        },
        "extra": manifest.extra,
    }


def grid_layout_to_dict(layout: GridLayout) -> Dict[str, Any]:
    """Convert a GridLayout to a JSON-serializable dictionary.

    Args:
        layout: The layout to convert.

    Returns:
        Dictionary representation of the layout.
    """
    return {
        "type": layout.type,
        "origin": layout.origin,
        "rows": layout.rows,
        "cols": layout.cols,
        "spacing": layout.spacing,
        "yaw_variation_deg": layout.yaw_variation_deg,
    }


def random_layout_to_dict(layout: RandomLayout) -> Dict[str, Any]:
    """Convert a RandomLayout to a JSON-serializable dictionary.

    Args:
        layout: The layout to convert.

    Returns:
        Dictionary representation of the layout.
    """
    return {
        "type": layout.type,
        "center": layout.center,
        "radius": layout.radius,
        "count": layout.count,
        "min_separation": layout.min_separation,
        "random_yaw": layout.random_yaw,
    }


# =============================================================================
# Tool Descriptions for LLM System Prompt
# =============================================================================


TOOL_DESCRIPTIONS = """
## Available Tools

### search_assets
Search for assets matching a natural language query.
- query: What to search for (e.g., "wooden crate", "farm vehicle", "camera")
- category: Optional filter - "environment", "robot", "prop", or "sensor"
- limit: Maximum results (default 10)
Returns: List of matching assets with id, name, category, and tags.

### get_asset_details
Get full details about a specific asset by its ID.
- asset_id: The asset identifier (e.g., "crate_wooden_small")
Returns: Complete asset info including physical size and placement rules.

### suggest_grid_layout
Create an organized grid arrangement for multiple objects.
- count: Total number of objects
- origin: [x, y, z] starting position
- max_per_row: Objects per row (default 5)
- spacing_xy: [dx, dy] distance between objects
Returns: Grid layout specification.

### suggest_random_layout
Create a natural scattered arrangement for objects.
- count: Number of objects
- center: [x, y, z] center of the area
- radius: Size of the spawn area
- min_separation: Minimum distance between objects
Returns: Random layout specification.
"""

