"""Asset manifest model and utilities."""

import json
from pathlib import Path
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class PlacementRules(BaseModel):
    """Rules for valid asset placement."""

    allow_on: List[str] = Field(default_factory=list)
    min_clearance: float = 0.0


class Semantics(BaseModel):
    """Semantic information for natural language matching."""

    human_names: List[str] = Field(default_factory=list)
    usage: List[str] = Field(default_factory=list)


class AssetManifest(BaseModel):
    """Manifest describing an asset's properties and metadata."""

    asset_id: str
    name: str
    category: Literal["environment", "robot", "prop", "sensor"]
    tags: List[str] = Field(default_factory=list)
    mjcf_include: str  # relative path to an XML include
    physical_size: Optional[List[float]] = None  # [x, y, z] meters
    placement_rules: PlacementRules = Field(default_factory=PlacementRules)
    semantics: Semantics = Field(default_factory=Semantics)
    extra: Dict[str, str] = Field(default_factory=dict)


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

