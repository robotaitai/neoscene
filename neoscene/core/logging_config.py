"""Logging configuration for Neoscene.

This module provides a centralized logging configuration for all Neoscene modules.
"""

import logging
import os
import sys
from typing import Optional

# Default log format
DEFAULT_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
DEFAULT_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Environment variable for log level
LOG_LEVEL_ENV = "NEOSCENE_LOG_LEVEL"


def get_log_level() -> int:
    """Get the log level from environment or default to INFO."""
    level_name = os.getenv(LOG_LEVEL_ENV, "INFO").upper()
    return getattr(logging, level_name, logging.INFO)


def setup_logging(
    level: Optional[int] = None,
    format_string: Optional[str] = None,
    log_file: Optional[str] = None,
) -> None:
    """Configure logging for Neoscene.

    Args:
        level: Log level (default: from env or INFO).
        format_string: Log format (default: DEFAULT_FORMAT).
        log_file: Optional file to log to (in addition to stderr).
    """
    if level is None:
        level = get_log_level()
    if format_string is None:
        format_string = DEFAULT_FORMAT

    # Create formatter
    formatter = logging.Formatter(format_string, datefmt=DEFAULT_DATE_FORMAT)

    # Configure root logger for neoscene
    root_logger = logging.getLogger("neoscene")
    root_logger.setLevel(level)

    # Remove existing handlers
    root_logger.handlers.clear()

    # Add stderr handler
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(formatter)
    stderr_handler.setLevel(level)
    root_logger.addHandler(stderr_handler)

    # Add file handler if requested
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        file_handler.setLevel(level)
        root_logger.addHandler(file_handler)


def get_logger(name: str) -> logging.Logger:
    """Get a logger for a Neoscene module.

    Args:
        name: Module name (typically __name__).

    Returns:
        Configured logger instance.
    """
    # Ensure logging is set up
    if not logging.getLogger("neoscene").handlers:
        setup_logging()

    return logging.getLogger(name)


# Convenience loggers for common modules
def get_agent_logger() -> logging.Logger:
    """Get logger for the scene agent."""
    return get_logger("neoscene.core.scene_agent")


def get_catalog_logger() -> logging.Logger:
    """Get logger for the asset catalog."""
    return get_logger("neoscene.core.asset_catalog")


def get_exporter_logger() -> logging.Logger:
    """Get logger for the MJCF exporter."""
    return get_logger("neoscene.exporters.mjcf_exporter")


def get_llm_logger() -> logging.Logger:
    """Get logger for the LLM client."""
    return get_logger("neoscene.core.llm_client")


def get_api_logger() -> logging.Logger:
    """Get logger for the API."""
    return get_logger("neoscene.app.api")

