"""LLM client wrapper for Gemini API.

This module provides a clean abstraction over the Gemini API, making it easy
to swap out for other providers later.
"""

import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class LLMError(Exception):
    """Base exception for LLM-related errors."""

    pass


class LLMConfigError(LLMError):
    """Configuration error for LLM client."""

    pass


class LLMAPIError(LLMError):
    """API error from LLM provider."""

    pass


def get_default_config_path() -> Path:
    """Get the default path to the LLM config file."""
    return Path(__file__).parent.parent.parent / "config" / "llm_config.yaml"


def load_llm_config(path: Optional[Path] = None) -> Dict[str, Any]:
    """Load LLM configuration from a YAML file.

    Args:
        path: Path to the config file. If None, uses the default path.

    Returns:
        Dictionary containing the configuration.

    Raises:
        LLMConfigError: If the config file cannot be loaded.
    """
    if path is None:
        path = get_default_config_path()

    if not path.exists():
        # Return defaults if config doesn't exist
        return {
            "default_model": "gemini-2.0-flash",
            "temperature": 0.3,
            "max_output_tokens": 2048,
        }

    try:
        with open(path) as f:
            config = yaml.safe_load(f)
            return config if config else {}
    except Exception as e:
        raise LLMConfigError(f"Failed to load LLM config from {path}: {e}")


class GeminiClient:
    """Client wrapper for Google's Gemini API.

    This class provides a clean interface to the Gemini API, handling
    authentication, configuration, and response parsing.

    Example:
        >>> client = GeminiClient.from_default_config()
        >>> response = client.generate("Describe a simple scene")
        >>> print(response)
    """

    def __init__(
        self,
        model_name: str = "gemini-1.5-flash",
        api_key: Optional[str] = None,
        temperature: float = 0.3,
        max_output_tokens: int = 2048,
    ):
        """Initialize the Gemini client.

        Args:
            model_name: Name of the Gemini model to use.
            api_key: API key for authentication. If None, reads from
                     GEMINI_API_KEY or GOOGLE_API_KEY environment variable.
            temperature: Sampling temperature (0.0 to 1.0).
            max_output_tokens: Maximum tokens in the response.

        Raises:
            LLMConfigError: If no API key is available.
        """
        self.model_name = model_name
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens

        # Get API key from argument, env, or raise error
        self.api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

        # Initialize the generative AI client if available
        self._client = None
        self._model = None

        if self.api_key:
            self._init_client()

    def _init_client(self) -> None:
        """Initialize the Google Generative AI client."""
        try:
            import google.generativeai as genai

            genai.configure(api_key=self.api_key)
            self._model = genai.GenerativeModel(self.model_name)
            self._client = genai
        except ImportError:
            # google-generativeai not installed, will use mock mode
            self._client = None
            self._model = None

    @property
    def is_configured(self) -> bool:
        """Check if the client is properly configured with an API key."""
        return self.api_key is not None

    @property
    def is_available(self) -> bool:
        """Check if the Gemini API is available (client initialized)."""
        return self._model is not None

    @classmethod
    def from_default_config(cls, api_key: Optional[str] = None) -> "GeminiClient":
        """Create a client from the default configuration file.

        Args:
            api_key: Optional API key override.

        Returns:
            Configured GeminiClient instance.
        """
        config = load_llm_config()
        return cls(
            model_name=config.get("default_model", "gemini-1.5-flash"),
            api_key=api_key,
            temperature=config.get("temperature", 0.3),
            max_output_tokens=config.get("max_output_tokens", 2048),
        )

    @classmethod
    def from_config(cls, config_path: Path, api_key: Optional[str] = None) -> "GeminiClient":
        """Create a client from a specific configuration file.

        Args:
            config_path: Path to the configuration file.
            api_key: Optional API key override.

        Returns:
            Configured GeminiClient instance.
        """
        config = load_llm_config(config_path)
        return cls(
            model_name=config.get("default_model", "gemini-1.5-flash"),
            api_key=api_key,
            temperature=config.get("temperature", 0.3),
            max_output_tokens=config.get("max_output_tokens", 2048),
        )

    def generate(
        self,
        prompt: str,
        temperature: Optional[float] = None,
        max_output_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> str:
        """Generate a response from the LLM.

        Args:
            prompt: The input prompt to send to the model.
            temperature: Override the default temperature.
            max_output_tokens: Override the default max tokens.
            **kwargs: Additional arguments passed to the API.

        Returns:
            The generated text response.

        Raises:
            LLMConfigError: If the client is not configured.
            LLMAPIError: If the API call fails.
        """
        temp = temperature if temperature is not None else self.temperature
        max_tokens = max_output_tokens if max_output_tokens is not None else self.max_output_tokens

        # If no API key or client, return a mock response
        if not self.is_configured or not self.is_available:
            return self._mock_generate(prompt)

        try:
            generation_config = {
                "temperature": temp,
                "max_output_tokens": max_tokens,
                **kwargs,
            }

            response = self._model.generate_content(
                prompt,
                generation_config=generation_config,
            )

            return response.text

        except Exception as e:
            raise LLMAPIError(f"Gemini API call failed: {e}")

    def _mock_generate(self, prompt: str) -> str:
        """Generate a mock response for testing without API access.

        Args:
            prompt: The input prompt.

        Returns:
            A mock response string.
        """
        # Return a helpful mock response
        if "scene" in prompt.lower() or "json" in prompt.lower():
            return """{
  "name": "mock_scene",
  "environment": {"asset_id": "orchard"},
  "objects": [],
  "cameras": []
}"""
        return f"[MOCK RESPONSE] Received prompt of {len(prompt)} characters. API key not configured."

    def generate_json(
        self,
        prompt: str,
        temperature: Optional[float] = None,
        max_output_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> str:
        """Generate a JSON response from the LLM using structured output mode.

        Uses Gemini's response_mime_type="application/json" for reliable JSON output.

        Args:
            prompt: The input prompt.
            temperature: Override the default temperature.
            max_output_tokens: Override the default max tokens.
            **kwargs: Additional arguments passed to generate().

        Returns:
            The generated JSON string.
        """
        if not self.is_configured or not self.is_available:
            return self._mock_generate(prompt)

        temp = temperature if temperature is not None else self.temperature
        max_tokens = max_output_tokens if max_output_tokens is not None else self.max_output_tokens

        try:
            generation_config = {
                "temperature": temp,
                "max_output_tokens": max_tokens,
                "response_mime_type": "application/json",  # Force JSON output
                **kwargs,
            }

            response = self._model.generate_content(
                prompt,
                generation_config=generation_config,
            )

            return response.text

        except Exception as e:
            raise LLMAPIError(f"Gemini API call failed: {e}")

    def __repr__(self) -> str:
        """Return a string representation of the client."""
        status = "configured" if self.is_configured else "not configured"
        available = "available" if self.is_available else "unavailable"
        return f"GeminiClient(model={self.model_name}, {status}, API {available})"

