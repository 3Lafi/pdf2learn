"""Per-job logging.

Each conversion run gets two log handlers:

- stdout: prefixed, human-friendly progress lines (suppressible via ``quiet``).
- ``conversion.log`` in the job's output directory: timestamped,
  retained regardless of whether the job succeeds or fails (FR-017).

Log messages use stable prefixes defined in ``contracts/cli.md``:
``[pdf2learn]``, ``[pdf2learn:warn]``, ``[pdf2learn:error]``.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

_LOGGER_NAME = "pdf2learn"

_FILE_FORMAT = "%(asctime)s %(levelname)s %(message)s"
_STDOUT_FORMAT = "%(message)s"


class _PrefixFormatter(logging.Formatter):
    """Inject the stable ``[pdf2learn:...]`` prefix for stdout lines."""

    def format(self, record: logging.LogRecord) -> str:
        if record.levelno >= logging.ERROR:
            prefix = "[pdf2learn:error]"
        elif record.levelno >= logging.WARNING:
            prefix = "[pdf2learn:warn]"
        else:
            prefix = "[pdf2learn]"
        record.message = record.getMessage()
        return f"{prefix} {record.message}"


def get_logger() -> logging.Logger:
    """Return the shared package logger, configured lazily on first call."""
    logger = logging.getLogger(_LOGGER_NAME)
    if getattr(logger, "_pdf2learn_configured", False):
        return logger
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    logger._pdf2learn_configured = True  # type: ignore[attr-defined]
    return logger


@contextmanager
def job_logging(log_path: Path, *, quiet: bool = False) -> Iterator[logging.Logger]:
    """Attach per-job handlers, yield the logger, and detach on exit.

    The file handler is opened before the ``yield`` and closed in ``finally``,
    so the ``conversion.log`` persists even if the body raises (FR-017).
    """
    logger = get_logger()

    log_path.parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(log_path, mode="w", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(_FILE_FORMAT))
    logger.addHandler(file_handler)

    stdout_handler: logging.Handler | None = None
    if not quiet:
        stdout_handler = logging.StreamHandler()
        stdout_handler.setLevel(logging.INFO)
        stdout_handler.setFormatter(_PrefixFormatter(_STDOUT_FORMAT))
        logger.addHandler(stdout_handler)

    try:
        yield logger
    finally:
        file_handler.close()
        logger.removeHandler(file_handler)
        if stdout_handler is not None:
            logger.removeHandler(stdout_handler)
