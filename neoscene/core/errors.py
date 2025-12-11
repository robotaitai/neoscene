"""Custom exceptions for Neoscene.

This module defines a hierarchy of exceptions used throughout Neoscene
for clear, actionable error messages.
"""

from typing import Any, Dict, List, Optional


class NeosceneError(Exception):
    """Base exception for all Neoscene errors.

    All Neoscene-specific exceptions inherit from this class,
    making it easy to catch all Neoscene errors.
    """

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to a dictionary for API responses."""
        return {
            "error": self.__class__.__name__,
            "message": self.message,
            "details": self.details,
        }


class AssetNotFoundError(NeosceneError):
    """Raised when a requested asset is not found in the catalog.

    Attributes:
        asset_id: The ID of the asset that was not found.
        category: The category that was searched (if any).
        suggestions: List of similar asset IDs that might help.
    """

    def __init__(
        self,
        asset_id: str,
        category: Optional[str] = None,
        suggestions: Optional[List[str]] = None,
    ):
        self.asset_id = asset_id
        self.category = category
        self.suggestions = suggestions or []

        message = f"Asset not found: '{asset_id}'"
        if category:
            message += f" in category '{category}'"
        if self.suggestions:
            message += f". Did you mean: {', '.join(self.suggestions[:3])}?"

        super().__init__(
            message,
            details={
                "asset_id": asset_id,
                "category": category,
                "suggestions": self.suggestions,
            },
        )


class SceneValidationError(NeosceneError):
    """Raised when scene validation fails.

    This can occur during:
    - JSON parsing of LLM output
    - Pydantic schema validation
    - Asset reference validation

    Attributes:
        validation_errors: List of specific validation error messages.
        raw_data: The raw data that failed validation (if available).
    """

    def __init__(
        self,
        message: str,
        validation_errors: Optional[List[str]] = None,
        raw_data: Optional[str] = None,
    ):
        self.validation_errors = validation_errors or []
        self.raw_data = raw_data

        super().__init__(
            message,
            details={
                "validation_errors": self.validation_errors,
                "raw_data_preview": raw_data[:500] if raw_data else None,
            },
        )


class LLMError(NeosceneError):
    """Raised when LLM operations fail.

    This can occur during:
    - API calls to Gemini
    - Response parsing
    - Rate limiting or quota issues

    Attributes:
        llm_provider: The LLM provider that failed (e.g., "gemini").
        original_error: The original exception if any.
    """

    def __init__(
        self,
        message: str,
        llm_provider: str = "gemini",
        original_error: Optional[Exception] = None,
    ):
        self.llm_provider = llm_provider
        self.original_error = original_error

        super().__init__(
            message,
            details={
                "llm_provider": llm_provider,
                "original_error": str(original_error) if original_error else None,
            },
        )


class LayoutError(NeosceneError):
    """Raised when a layout cannot be generated.

    This can occur when:
    - Random layout can't place enough objects with min_separation
    - Grid layout parameters are invalid
    - Layout conflicts with environment bounds

    Attributes:
        layout_type: The type of layout that failed (grid/random).
        count: Number of objects that couldn't be placed.
    """

    def __init__(
        self,
        message: str,
        layout_type: str,
        count: Optional[int] = None,
    ):
        self.layout_type = layout_type
        self.count = count

        super().__init__(
            message,
            details={
                "layout_type": layout_type,
                "count": count,
            },
        )


class MJCFExportError(NeosceneError):
    """Raised when MJCF export fails.

    This can occur when:
    - Asset MJCF files are missing or invalid
    - XML generation fails

    Attributes:
        asset_id: The asset that caused the failure (if any).
    """

    def __init__(self, message: str, asset_id: Optional[str] = None):
        self.asset_id = asset_id

        super().__init__(
            message,
            details={"asset_id": asset_id},
        )


class ConfigurationError(NeosceneError):
    """Raised when configuration is invalid or missing.

    This can occur when:
    - API key is missing
    - Config file is malformed
    - Required settings are not provided
    """

    def __init__(self, message: str, config_key: Optional[str] = None):
        self.config_key = config_key

        super().__init__(
            message,
            details={"config_key": config_key},
        )

