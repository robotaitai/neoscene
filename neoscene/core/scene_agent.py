"""Scene Agent - converts natural language to SceneSpec.

This module provides the SceneAgent class that orchestrates the conversion
of natural language scene descriptions into valid SceneSpec objects using
the LLM and asset catalog.
"""

import json
import re
from typing import Any, Dict, List, Optional

from pydantic import ValidationError

from neoscene.core.asset_catalog import AssetCatalog
from neoscene.core.errors import LLMError, NeosceneError, SceneValidationError
from neoscene.core.llm_client import GeminiClient, LLMAPIError
from neoscene.core.logging_config import get_logger
from neoscene.core.scene_schema import SceneSpec
from neoscene.core.scene_tools import list_assets_by_category

logger = get_logger(__name__)


class SceneGenerationError(NeosceneError):
    """Error during scene generation."""

    pass


def _build_asset_catalog_summary(catalog: AssetCatalog) -> str:
    """Build a summary of available assets for the LLM.

    Args:
        catalog: The asset catalog.

    Returns:
        Formatted string describing available assets.
    """
    lines = ["## Available Assets\n"]

    for category in ["environment", "robot", "prop", "sensor"]:
        assets = list_assets_by_category(catalog, category=category)
        if assets:
            lines.append(f"### {category.title()}s")
            for asset in assets:
                tags = ", ".join(asset["tags"][:5])
                lines.append(f"- `{asset['asset_id']}`: {asset['name']} (tags: {tags})")
            lines.append("")

    return "\n".join(lines)


def _build_schema_summary() -> str:
    """Build a summary of the SceneSpec schema for the LLM.

    Returns:
        Formatted string describing the schema.
    """
    return """## SceneSpec JSON Schema

```json
{
  "name": "string (required) - unique scene name",
  "description": "string (optional) - human description",
  "environment": {
    "asset_id": "string (required) - must be from Available Assets",
    "gravity": [0.0, 0.0, -9.81] (optional)
  },
  "objects": [
    {
      "asset_id": "string (required) - must be from Available Assets",
      "name": "string (optional) - display name",
      "instances": [
        {
          "pose": {
            "position": [x, y, z] (required),
            "yaw_deg": 0.0 (optional),
            "pitch_deg": 0.0 (optional),
            "roll_deg": 0.0 (optional)
          }
        }
      ]
      // OR use layout instead of instances:
      "layout": {
        "type": "grid",
        "origin": [x, y, z],
        "rows": int,
        "cols": int,
        "spacing": [dx, dy]
      }
      // OR:
      "layout": {
        "type": "random",
        "center": [x, y, z],
        "radius": float,
        "count": int,
        "min_separation": float
      }
    }
  ],
  "cameras": [
    {
      "name": "string (required)",
      "pose": {
        "position": [x, y, z],
        "yaw_deg": 0.0,
        "pitch_deg": 0.0
      },
      "target": [x, y, z] (optional - look-at point),
      "fovy": 45.0 (optional)
    }
  ],
  "lights": [
    {
      "name": "string",
      "type": "directional" | "point" | "spot",
      "position": [x, y, z],
      "direction": [dx, dy, dz] (for directional),
      "diffuse": [r, g, b]
    }
  ],
  "physics": {
    "timestep": 0.002,
    "solver": "Newton"
  }
}
```

### Important Rules:
1. All asset_id values MUST exactly match an ID from Available Assets
2. Position coordinates are in meters (x=right, y=forward, z=up)
3. For multiple objects, use either `instances` OR `layout`, not both
4. For grid layout: total objects = rows × cols
5. Environment is required, objects/cameras/lights are optional
"""


def _extract_json_from_response(response: str) -> str:
    """Extract JSON from an LLM response that might include markdown.

    Args:
        response: Raw LLM response.

    Returns:
        Extracted JSON string.

    Raises:
        SceneGenerationError: If no valid JSON found.
    """
    # Try to find JSON in markdown code blocks
    json_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", response, re.DOTALL)
    if json_match:
        return json_match.group(1).strip()

    # Try to find raw JSON (starts with { and ends with })
    json_match = re.search(r"\{.*\}", response, re.DOTALL)
    if json_match:
        return json_match.group(0).strip()

    # If response looks like pure JSON
    stripped = response.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        return stripped

    raise SceneGenerationError(f"Could not extract JSON from response: {response[:200]}...")


class SceneAgent:
    """Agent that converts natural language prompts to SceneSpec.

    The SceneAgent uses an LLM to interpret user descriptions and generate
    valid scene specifications that reference assets from the catalog.

    Example:
        >>> catalog = AssetCatalog(Path("neoscene/assets"))
        >>> llm = GeminiClient.from_default_config()
        >>> agent = SceneAgent(catalog, llm)
        >>> spec = agent.generate_scene_spec("An orchard with a tractor")
        >>> print(spec.name)

    TODO(future): Add multi-turn conversation for iterative refinement
    TODO(future): Use LLM function calling for structured tool use
    TODO(future): Add streaming support for real-time feedback
    TODO(future): Implement scene templates for common scenarios
    """

    def __init__(
        self,
        catalog: AssetCatalog,
        llm: GeminiClient,
        max_repair_attempts: int = 2,
    ):
        """Initialize the SceneAgent.

        Args:
            catalog: Asset catalog for available assets.
            llm: LLM client for generation.
            max_repair_attempts: Max attempts to repair invalid JSON.
        """
        self.catalog = catalog
        self.llm = llm
        self.max_repair_attempts = max_repair_attempts

        # Pre-build the asset summary
        self._asset_summary = _build_asset_catalog_summary(catalog)
        self._schema_summary = _build_schema_summary()

        logger.info(f"SceneAgent initialized with {len(catalog)} assets")

    def _build_system_prompt(self) -> str:
        """Build the system prompt for scene generation."""
        return f"""You are a scene generation assistant for MuJoCo simulations.
Your task is to convert natural language scene descriptions into valid JSON
that conforms to the SceneSpec schema.

{self._asset_summary}

{self._schema_summary}

## Instructions:
1. Read the user's scene description carefully
2. Choose appropriate assets from the Available Assets list
3. Position objects logically in 3D space (z=0 is ground level)
4. Use layouts (grid/random) for multiple similar objects
5. Add at least one camera to observe the scene
6. Return ONLY valid JSON, no explanations or markdown
"""

    def _build_user_prompt(self, user_prompt: str, previous_scene: Optional[SceneSpec] = None) -> str:
        """Build the user prompt for scene generation.
        
        Args:
            user_prompt: The user's natural language request.
            previous_scene: Optional previous scene to modify.
        """
        if previous_scene is None:
            return f"""Create a SceneSpec JSON for this scene:

"{user_prompt}"

Remember:
- Use ONLY asset_id values from the Available Assets list
- Position objects logically (z=0 is ground, positive z is up)
- Include at least one camera
- Return ONLY the JSON object, no markdown or explanations"""
        
        # Include previous scene for modification
        import json
        prev_json = json.dumps(previous_scene.model_dump(), indent=2)
        
        return f"""Here is the CURRENT scene:

```json
{prev_json}
```

The user wants to MODIFY this scene with the following request:

"{user_prompt}"

Instructions:
- Start from the current scene and apply the user's modifications
- Keep existing objects/cameras unless the user asks to remove them
- Add new objects where specified
- Modify positions, counts, or layouts as requested
- Use ONLY asset_id values from the Available Assets list
- Return the COMPLETE modified scene as JSON (not just the changes)
- Return ONLY the JSON object, no markdown or explanations"""

    def generate_scene_spec(
        self, 
        user_prompt: str, 
        previous_scene: Optional[SceneSpec] = None
    ) -> SceneSpec:
        """Generate a SceneSpec from a natural language prompt.

        Args:
            user_prompt: Natural language description of the desired scene.
            previous_scene: Optional previous scene to modify (for incremental updates).

        Returns:
            Valid SceneSpec object.

        Raises:
            LLMError: If LLM generation fails.
            SceneValidationError: If the generated JSON is invalid.
        """
        if previous_scene:
            logger.info(f"Updating scene '{previous_scene.name}' with: '{user_prompt[:100]}...'")
        else:
            logger.info(f"Generating scene for prompt: '{user_prompt[:100]}...'")

        system_prompt = self._build_system_prompt()
        user_message = self._build_user_prompt(user_prompt, previous_scene)
        full_prompt = f"{system_prompt}\n\n---\n\n{user_message}"

        try:
            raw_response = self.llm.generate(
                full_prompt,
                temperature=0.3,  # Lower for more consistent output
            )
            logger.debug(f"LLM response received: {len(raw_response)} chars")
        except LLMAPIError as e:
            logger.error(f"LLM generation failed: {e}")
            raise LLMError(
                f"LLM generation failed: {e}",
                llm_provider="gemini",
                original_error=e,
            )

        spec = self._parse_and_validate(raw_response, user_prompt)

        logger.info(
            f"Generated scene: name='{spec.name}', "
            f"env='{spec.environment.asset_id}', "
            f"objects={len(spec.objects)}, cameras={len(spec.cameras)}"
        )

        return spec

    def _parse_and_validate(
        self,
        raw_response: str,
        original_prompt: str,
    ) -> SceneSpec:
        """Parse and validate the LLM response.

        Args:
            raw_response: Raw LLM response.
            original_prompt: Original user prompt (for error context).

        Returns:
            Validated SceneSpec.

        Raises:
            SceneValidationError: If validation fails.
        """
        # Extract JSON from response
        try:
            json_str = _extract_json_from_response(raw_response)
        except SceneGenerationError:
            logger.warning("Could not extract JSON from LLM response")
            raise SceneValidationError(
                "Could not extract JSON from LLM response",
                validation_errors=["No valid JSON found in response"],
                raw_data=raw_response,
            )

        # Parse JSON
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.warning(f"Invalid JSON: {e}")
            raise SceneValidationError(
                f"Invalid JSON: {e}",
                validation_errors=[str(e)],
                raw_data=json_str,
            )

        # Validate with Pydantic
        try:
            spec = SceneSpec.model_validate(data)
        except ValidationError as e:
            errors = [f"{err['loc']}: {err['msg']}" for err in e.errors()]
            logger.warning(f"Schema validation failed: {len(errors)} errors")
            raise SceneValidationError(
                f"SceneSpec validation failed: {len(errors)} errors",
                validation_errors=errors,
                raw_data=json_str,
            )

        # Validate asset IDs exist in catalog
        validation_errors = self._validate_asset_references(spec)
        if validation_errors:
            logger.warning(f"Asset validation failed: {validation_errors}")
            raise SceneValidationError(
                f"Invalid asset references: {len(validation_errors)} errors",
                validation_errors=validation_errors,
                raw_data=json_str,
            )

        return spec

    def _validate_asset_references(self, spec: SceneSpec) -> List[str]:
        """Validate that all asset_id references exist in the catalog.

        Args:
            spec: The SceneSpec to validate.

        Returns:
            List of validation error messages.
        """
        errors = []

        # Check environment
        if spec.environment.asset_id not in self.catalog:
            available = [a["asset_id"] for a in list_assets_by_category(self.catalog, "environment")]
            errors.append(
                f"Environment asset_id '{spec.environment.asset_id}' not found. "
                f"Available: {available}"
            )

        # Check objects
        for obj in spec.objects:
            if obj.asset_id not in self.catalog:
                # Try to find similar assets
                similar = [
                    a["asset_id"]
                    for a in list_assets_by_category(self.catalog)
                    if obj.asset_id.lower() in a["asset_id"].lower()
                    or a["asset_id"].lower() in obj.asset_id.lower()
                ]
                errors.append(
                    f"Object asset_id '{obj.asset_id}' not found. "
                    f"Similar: {similar if similar else 'none'}"
                )

        # Check cameras with asset_id
        for cam in spec.cameras:
            if cam.asset_id and cam.asset_id not in self.catalog:
                errors.append(f"Camera asset_id '{cam.asset_id}' not found")

        return errors

    def generate_and_repair(
        self, 
        user_prompt: str,
        previous_scene: Optional[SceneSpec] = None
    ) -> SceneSpec:
        """Generate a SceneSpec with automatic repair on failure.

        This method attempts to generate a scene, and if validation fails,
        it sends the errors back to the LLM for correction.

        Args:
            user_prompt: Natural language description of the desired scene.
            previous_scene: Optional previous scene to modify (for incremental updates).

        Returns:
            Valid SceneSpec object.

        Raises:
            SceneGenerationError: If generation fails after all repair attempts.
        """
        last_error: Optional[SceneValidationError] = None

        for attempt in range(self.max_repair_attempts + 1):
            try:
                if attempt == 0:
                    return self.generate_scene_spec(user_prompt, previous_scene)
                else:
                    logger.info(f"Repair attempt {attempt}/{self.max_repair_attempts}")
                    return self._repair_scene_spec(
                        user_prompt,
                        last_error.raw_data,
                        last_error.validation_errors,
                    )
            except SceneValidationError as e:
                last_error = e
                if attempt < self.max_repair_attempts:
                    continue
                logger.error(f"Failed after {self.max_repair_attempts + 1} attempts")
                raise SceneGenerationError(
                    f"Failed to generate valid scene after {self.max_repair_attempts + 1} attempts. "
                    f"Last errors: {e.validation_errors}"
                )

        raise SceneGenerationError("Unexpected error in generate_and_repair")

    def _repair_scene_spec(
        self,
        original_prompt: str,
        invalid_json: str,
        errors: List[str],
    ) -> SceneSpec:
        """Attempt to repair an invalid SceneSpec.

        Args:
            original_prompt: Original user prompt.
            invalid_json: The invalid JSON that was generated.
            errors: List of validation errors.

        Returns:
            Repaired SceneSpec.

        Raises:
            SceneValidationError: If repair fails.
        """
        repair_prompt = f"""{self._build_system_prompt()}

---

The previous attempt to generate a scene for "{original_prompt}" produced invalid JSON.

## Invalid JSON:
```json
{invalid_json}
```

## Validation Errors:
{chr(10).join(f'- {e}' for e in errors)}

## Instructions:
Fix the JSON to resolve all validation errors. Return ONLY the corrected JSON, no explanations.
Remember to use ONLY asset_id values from the Available Assets list."""

        try:
            raw_response = self.llm.generate(repair_prompt, temperature=0.2)
        except LLMAPIError as e:
            raise LLMError(
                f"LLM repair failed: {e}",
                llm_provider="gemini",
                original_error=e,
            )

        return self._parse_and_validate(raw_response, original_prompt)

    def suggest_scene(self, user_prompt: str) -> Dict[str, Any]:
        """Get a scene suggestion as a dictionary (for debugging/preview).

        This is useful for inspecting what the LLM generates before
        full validation.

        Args:
            user_prompt: Natural language description.

        Returns:
            Raw dictionary from LLM (may not be valid SceneSpec).
        """
        system_prompt = self._build_system_prompt()
        user_message = self._build_user_prompt(user_prompt)
        full_prompt = f"{system_prompt}\n\n---\n\n{user_message}"

        try:
            raw_response = self.llm.generate(full_prompt, temperature=0.3)
            json_str = _extract_json_from_response(raw_response)
            return json.loads(json_str)
        except (LLMAPIError, json.JSONDecodeError, SceneGenerationError) as e:
            logger.warning(f"suggest_scene failed: {e}")
            return {"error": str(e)}
