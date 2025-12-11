"""Asset manifest model and utilities.

The manifest is the SINGLE SOURCE OF TRUTH for asset semantics.
All category/tag/fallback information lives here - no external config.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


# Standardized categories
AssetCategory = Literal[
    "environment",  # terrain, ground, world backgrounds
    "vehicle",      # tractors, cars, trucks, robots with wheels
    "nature",       # trees, rocks, grass, bushes, vegetation
    "urban",        # buildings, roads, street lights, signs
    "sensor",       # cameras, IMUs, LiDARs, GPS
    "person",       # humans, pedestrians
    "animal",       # birds, dogs, farm animals
    "prop",         # crates, barrels, cones, tools
    # Legacy categories (for backward compatibility)
    "robot",        # alias for vehicle
]

# Sensor subtypes
SensorType = Literal["camera", "imu", "lidar", "gps", "rangefinder", "depth", "other"]

# Availability status
Availability = Literal["local", "remote"]


class PlacementRules(BaseModel):
    """Rules for valid asset placement."""

    allow_on: List[str] = Field(default_factory=list)
    min_clearance: float = 0.0


class Semantics(BaseModel):
    """Semantic information for natural language matching."""

    human_names: List[str] = Field(default_factory=list)
    usage: List[str] = Field(default_factory=list)


class AssetManifest(BaseModel):
    """Manifest describing an asset's properties and metadata.
    
    This is the SINGLE SOURCE OF TRUTH for asset semantics.
    
    Key fields for LLM matching:
    - tags: List of words/concepts this asset matches
    - fallback_for: List of concepts this asset can substitute for
    - sensor_type: For sensors, what kind (camera, imu, lidar, etc.)
    
    Example manifest:
        asset_id: "car_generic"
        category: "vehicle"
        tags: ["car", "vehicle", "pickup"]
        fallback_for: ["tractor"]  # Can substitute for tractor if none available
    """

    # Required identification
    asset_id: str
    name: str
    category: AssetCategory
    
    # Semantic matching (IMPORTANT for LLM)
    tags: List[str] = Field(default_factory=list)
    fallback_for: List[str] = Field(
        default_factory=list,
        description="Concepts this asset can substitute for if primary not available"
    )
    
    # Sensor-specific
    sensor_type: Optional[SensorType] = Field(
        default=None,
        description="For category='sensor', what type of sensor"
    )
    
    # Asset location
    availability: Availability = Field(
        default="local",
        description="Whether asset is local or needs download"
    )
    remote_url: Optional[str] = Field(
        default=None,
        description="URL to download if availability='remote'"
    )
    
    # Physical properties
    mjcf_include: str  # relative path to MJCF XML
    physical_size: Optional[List[float]] = None  # [x, y, z] meters
    
    # Placement and semantics
    placement_rules: PlacementRules = Field(default_factory=PlacementRules)
    semantics: Semantics = Field(default_factory=Semantics)
    
    # Extension point
    extra: Dict[str, Any] = Field(default_factory=dict)
    
    def to_llm_summary(self) -> Dict[str, Any]:
        """Convert to a compact dict for LLM prompts.
        
        Only includes fields relevant for LLM asset selection.
        """
        result = {
            "asset_id": self.asset_id,
            "name": self.name,
            "tags": self.tags,
        }
        if self.fallback_for:
            result["fallback_for"] = self.fallback_for
        if self.sensor_type:
            result["sensor_type"] = self.sensor_type
        if self.availability == "remote":
            result["availability"] = "remote"
        return result


def load_manifest(path: Path) -> AssetManifest:
    """Load and validate an asset manifest from a JSON file.

    Args:
        path: Path to the manifest.json file.

    Returns:
        Validated AssetManifest instance.

    Raises:
        FileNotFoundError: If the manifest file doesn't exist.
        json.JSONDecodeError: If the file contains invalid JSON.
        pydantic.ValidationError: If the manifest doesn't match the schema.
    """
    data = json.loads(path.read_text())
    return AssetManifest.model_validate(data)


def discover_manifests(assets_dir: Path) -> List[Path]:
    """Discover all manifest.json files in the assets directory.

    Args:
        assets_dir: Path to the assets directory.

    Returns:
        List of paths to manifest.json files.
    """
    return list(assets_dir.glob("**/manifest.json"))

