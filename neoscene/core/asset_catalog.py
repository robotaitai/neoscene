"""Asset catalog for managing and searching assets.

The catalog is the runtime index over asset manifests.
It provides APIs for:
- Fuzzy text matching (best_match)
- Fallback resolution (fallback_for)
- Category/tag filtering
- LLM prompt generation (grouped by category)
"""

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
    fallback_for: List[str] = []
    sensor_type: Optional[str] = None
    availability: str = "local"
    path: Path  # path to the asset folder (parent of manifest.json)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to a dictionary suitable for LLM tools.

        Returns:
            Dictionary representation with path as string.
        """
        result = {
            "asset_id": self.asset_id,
            "name": self.name,
            "category": self.category,
            "tags": self.tags,
        }
        if self.fallback_for:
            result["fallback_for"] = self.fallback_for
        if self.sensor_type:
            result["sensor_type"] = self.sensor_type
        if self.availability == "remote":
            result["availability"] = "remote"
        return result


class AssetCatalog:
    """Catalog for managing and searching assets.

    The catalog scans asset directories, loads manifests, and provides
    APIs for finding assets by text, tags, category, or fallback.

    Key APIs:
        best_match(text, category) - Find best asset matching a concept
        fallback_for(concept) - Find asset that can substitute for a concept
        for_llm_prompt() - Get grouped asset list for LLM prompts

    Example:
        >>> catalog = AssetCatalog(Path("neoscene/assets"))
        >>> tractor = catalog.best_match("tractor", category="vehicle")
        >>> print(tractor.name)
        'Blue & White Tractor'
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
        
        # Indices for fast lookup
        self._by_category: Dict[str, List[str]] = {}  # category -> [asset_ids]
        self._by_tag: Dict[str, List[str]] = {}  # tag -> [asset_ids]
        self._by_fallback: Dict[str, List[str]] = {}  # concept -> [asset_ids that can substitute]
        
        self._scan()

    def _scan(self) -> None:
        """Scan the root directory for manifest.json files and load them."""
        self._by_id.clear()
        self._paths.clear()
        self._summaries.clear()
        self._by_category.clear()
        self._by_tag.clear()
        self._by_fallback.clear()

        logger.info(f"Scanning assets in {self.root_dir}")

        for manifest_path in self.root_dir.glob("**/manifest.json"):
            try:
                manifest = load_manifest(manifest_path)
                asset_folder = manifest_path.parent
                aid = manifest.asset_id

                self._by_id[aid] = manifest
                self._paths[aid] = asset_folder

                summary = AssetSummary(
                    asset_id=aid,
                    name=manifest.name,
                    category=manifest.category,
                    tags=manifest.tags,
                    fallback_for=manifest.fallback_for,
                    sensor_type=manifest.sensor_type,
                    availability=manifest.availability,
                    path=asset_folder,
                )
                self._summaries.append(summary)
                
                # Build category index
                cat = manifest.category
                if cat not in self._by_category:
                    self._by_category[cat] = []
                self._by_category[cat].append(aid)
                
                # Build tag index
                for tag in manifest.tags:
                    tag_lower = tag.lower()
                    if tag_lower not in self._by_tag:
                        self._by_tag[tag_lower] = []
                    self._by_tag[tag_lower].append(aid)
                
                # Build fallback index
                for concept in manifest.fallback_for:
                    concept_lower = concept.lower()
                    if concept_lower not in self._by_fallback:
                        self._by_fallback[concept_lower] = []
                    self._by_fallback[concept_lower].append(aid)

                logger.debug(f"Loaded asset: {aid} ({cat})")

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

    def best_match(
        self,
        text: str,
        category: Optional[str] = None,
        prefer_local: bool = True,
    ) -> Optional[AssetManifest]:
        """Find the best asset matching a concept/text.

        Uses fuzzy matching on tags, name, and semantic fields.
        Prefers local assets over remote ones.

        Args:
            text: Concept or search text (e.g., "tractor", "apple tree")
            category: Optional category filter
            prefer_local: If True, prefer local assets over remote

        Returns:
            Best matching AssetManifest, or None if no match.
        """
        results = self.search(text, category=category, limit=10)
        
        if not results:
            return None
        
        # Filter by availability if preferred
        if prefer_local:
            local_results = [r for r in results if r.availability == "local"]
            if local_results:
                return self._by_id[local_results[0].asset_id]
        
        return self._by_id[results[0].asset_id]

    def find_fallback(
        self,
        concept: str,
        category: Optional[str] = None,
    ) -> Optional[AssetManifest]:
        """Find an asset that can substitute for a concept.

        Looks for assets whose `fallback_for` list includes the concept.

        Args:
            concept: The concept to find a fallback for (e.g., "tractor")
            category: Optional category filter

        Returns:
            AssetManifest that can substitute, or None.
        """
        concept_lower = concept.lower()
        
        # Check fallback index
        if concept_lower in self._by_fallback:
            candidates = self._by_fallback[concept_lower]
            
            for aid in candidates:
                manifest = self._by_id[aid]
                # Filter by category if specified
                if category and manifest.category != category:
                    continue
                # Prefer local
                if manifest.availability == "local":
                    return manifest
            
            # Return first remote if no local
            if candidates:
                return self._by_id[candidates[0]]
        
        return None

    def resolve_asset(
        self,
        concept: str,
        category: Optional[str] = None,
    ) -> Optional[AssetManifest]:
        """Resolve a concept to an asset, using fallback if needed.

        First tries direct match, then falls back to fallback_for.

        Args:
            concept: The concept to resolve (e.g., "tractor")
            category: Optional category filter

        Returns:
            Best matching AssetManifest, or None.
        """
        # Try direct match first
        direct = self.best_match(concept, category=category)
        if direct:
            return direct
        
        # Try fallback
        return self.find_fallback(concept, category=category)

    def for_llm_prompt(self, local_only: bool = True) -> Dict[str, List[Dict[str, Any]]]:
        """Generate asset catalog grouped by category for LLM prompts.

        Returns a dict keyed by category, each containing a list of
        asset summaries suitable for including in an LLM prompt.

        Args:
            local_only: If True, only include locally available assets

        Returns:
            Dict like:
            {
                "vehicle": [
                    {"asset_id": "tractor_bluewhite", "tags": ["tractor", "farm"]},
                    ...
                ],
                "nature": [...],
                ...
            }
        """
        result: Dict[str, List[Dict[str, Any]]] = {}
        
        for summary in self._summaries:
            # Skip remote if local_only
            if local_only and summary.availability == "remote":
                continue
            
            cat = summary.category
            if cat not in result:
                result[cat] = []
            
            result[cat].append(summary.to_dict())
        
        return result

    def categories(self) -> List[str]:
        """Return list of all categories that have assets."""
        return list(self._by_category.keys())

    def __len__(self) -> int:
        """Return the number of assets in the catalog."""
        return len(self._by_id)

    def __contains__(self, asset_id: str) -> bool:
        """Check if an asset exists in the catalog."""
        return asset_id in self._by_id
