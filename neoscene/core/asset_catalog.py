"""Asset catalog for managing and searching assets."""

from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict

from neoscene.core.asset_manifest import AssetManifest, load_manifest
from neoscene.core.errors import AssetNotFoundError
from neoscene.core.logging_config import get_logger

logger = get_logger(__name__)


class AssetSummary(BaseModel):
    """Lightweight view of an asset for search results."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    asset_id: str
    name: str
    category: str
    tags: List[str]
    path: Path  # path to the asset folder (parent of manifest.json)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to a dictionary suitable for LLM tools.

        Returns:
            Dictionary representation with path as string.
        """
        return {
            "asset_id": self.asset_id,
            "name": self.name,
            "category": self.category,
            "tags": self.tags,
            "path": str(self.path),
        }


class AssetCatalog:
    """Catalog for managing and searching assets.

    The catalog scans asset directories, loads manifests, and provides
    a simple search API for finding assets by text, tags, or category.

    Example:
        >>> catalog = AssetCatalog(Path("neoscene/assets"))
        >>> results = catalog.search("crate")
        >>> print(results[0].name)
        'Small Wooden Crate'

    TODO(future): Add vector/embedding-based semantic search
    TODO(future): Cache asset thumbnails for UI preview
    TODO(future): Support remote asset repositories
    TODO(future): Add asset validation CLI tool
    """

    def __init__(self, root_dir: Path) -> None:
        """Initialize the asset catalog.

        Args:
            root_dir: Root directory containing asset subdirectories.
        """
        self.root_dir = root_dir
        self._by_id: Dict[str, AssetManifest] = {}
        self._paths: Dict[str, Path] = {}  # asset_id -> folder path
        self._summaries: List[AssetSummary] = []
        self._scan()

    def _scan(self) -> None:
        """Scan the root directory for manifest.json files and load them."""
        self._by_id.clear()
        self._paths.clear()
        self._summaries.clear()

        logger.info(f"Scanning assets in {self.root_dir}")

        for manifest_path in self.root_dir.glob("**/manifest.json"):
            try:
                manifest = load_manifest(manifest_path)
                asset_folder = manifest_path.parent

                self._by_id[manifest.asset_id] = manifest
                self._paths[manifest.asset_id] = asset_folder

                summary = AssetSummary(
                    asset_id=manifest.asset_id,
                    name=manifest.name,
                    category=manifest.category,
                    tags=manifest.tags,
                    path=asset_folder,
                )
                self._summaries.append(summary)
                logger.debug(f"Loaded asset: {manifest.asset_id} ({manifest.category})")

            except Exception as e:
                logger.warning(f"Failed to load {manifest_path}: {e}")

        logger.info(f"Loaded {len(self._by_id)} assets")

    def _find_similar(self, asset_id: str, limit: int = 3) -> List[str]:
        """Find similar asset IDs for error suggestions.

        Args:
            asset_id: The asset ID that was not found.
            limit: Maximum number of suggestions.

        Returns:
            List of similar asset IDs.
        """
        suggestions = []
        query_lower = asset_id.lower()

        for existing_id in self._by_id:
            # Check for partial matches
            if query_lower in existing_id.lower() or existing_id.lower() in query_lower:
                suggestions.append(existing_id)
            # Check for common prefix
            elif len(query_lower) > 3 and existing_id.lower().startswith(query_lower[:3]):
                suggestions.append(existing_id)

        return suggestions[:limit]

    def _score(self, summary: AssetSummary, query: str) -> int:
        """Calculate a relevance score for a query against an asset.

        Higher scores indicate better matches.

        Args:
            summary: The asset summary to score.
            query: The search query (lowercase).

        Returns:
            Integer score (higher is better, 0 means no match).
        """
        score = 0
        query_lower = query.lower()

        # Exact match in asset_id (highest priority)
        if query_lower == summary.asset_id.lower():
            score += 100

        # Partial match in asset_id
        elif query_lower in summary.asset_id.lower():
            score += 50

        # Exact match in name
        if query_lower == summary.name.lower():
            score += 80

        # Partial match in name
        elif query_lower in summary.name.lower():
            score += 40

        # Match in tags
        for tag in summary.tags:
            if query_lower == tag.lower():
                score += 30
            elif query_lower in tag.lower():
                score += 15

        # Match in semantics (human_names and usage) via full manifest
        manifest = self._by_id.get(summary.asset_id)
        if manifest and manifest.semantics:
            for human_name in manifest.semantics.human_names:
                if query_lower == human_name.lower():
                    score += 25
                elif query_lower in human_name.lower():
                    score += 12

            for usage in manifest.semantics.usage:
                if query_lower == usage.lower():
                    score += 20
                elif query_lower in usage.lower():
                    score += 10

        return score

    def search(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 10,
    ) -> List[AssetSummary]:
        """Search for assets matching a query.

        Args:
            query: Search query string.
            category: Optional category filter (environment, robot, prop, sensor).
            limit: Maximum number of results to return.

        Returns:
            List of matching AssetSummary objects, sorted by relevance.
        """
        logger.debug(f"Searching assets: query='{query}', category={category}")
        results: List[tuple[int, AssetSummary]] = []

        for summary in self._summaries:
            # Filter by category if specified
            if category and summary.category != category:
                continue

            score = self._score(summary, query)
            if score > 0:
                results.append((score, summary))

        # Sort by score (descending) and return top results
        results.sort(key=lambda x: x[0], reverse=True)
        found = [summary for _, summary in results[:limit]]
        logger.debug(f"Found {len(found)} assets matching '{query}'")
        return found

    def get(self, asset_id: str) -> AssetManifest:
        """Get the full manifest for an asset by ID.

        Args:
            asset_id: The unique asset identifier.

        Returns:
            The full AssetManifest for the asset.

        Raises:
            AssetNotFoundError: If no asset with the given ID exists.
        """
        if asset_id not in self._by_id:
            suggestions = self._find_similar(asset_id)
            logger.warning(f"Asset not found: {asset_id}")
            raise AssetNotFoundError(asset_id, suggestions=suggestions)
        return self._by_id[asset_id]

    def get_path(self, asset_id: str) -> Path:
        """Get the folder path for an asset by ID.

        Args:
            asset_id: The unique asset identifier.

        Returns:
            Path to the asset's folder.

        Raises:
            AssetNotFoundError: If no asset with the given ID exists.
        """
        if asset_id not in self._paths:
            suggestions = self._find_similar(asset_id)
            raise AssetNotFoundError(asset_id, suggestions=suggestions)
        return self._paths[asset_id]

    def list_all(self, category: Optional[str] = None) -> List[AssetSummary]:
        """List all assets, optionally filtered by category.

        Args:
            category: Optional category filter.

        Returns:
            List of all matching AssetSummary objects.
        """
        if category:
            return [s for s in self._summaries if s.category == category]
        return list(self._summaries)

    def __len__(self) -> int:
        """Return the number of assets in the catalog."""
        return len(self._by_id)

    def __contains__(self, asset_id: str) -> bool:
        """Check if an asset exists in the catalog."""
        return asset_id in self._by_id
