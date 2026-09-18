"""Project-wide logging configuration."""

from __future__ import annotations

import logging
import os


def configure_logging() -> None:
    """Configure root logger. Reads `LOG_LEVEL` from env with fallback to INFO."""
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    log_format = "%(asctime)s %(levelname)s %(name)s: %(message)s"
    logging.basicConfig(level=level, format=log_format)

    # Reduce verbosity from common noisy libraries
    for noisy in ("urllib3", "httpx", "charset_normalizer", "asyncio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


configure_logging()
