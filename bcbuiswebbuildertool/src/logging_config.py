"""
Central logging configuration for Pacific Web Builder.

Why a custom stdout handler? The admin server captures per-job output by
temporarily redirecting ``sys.stdout`` to a ``_JobLogger`` (see server.py),
which feeds the live SSE log stream in the dashboard. A stock
``logging.StreamHandler(sys.stdout)`` binds to the stdout object at
construction time and would miss that redirect. ``_StdoutHandler`` resolves
``sys.stdout`` at emit time instead, so every ``log.info(...)`` call inside a
running job is still captured and streamed exactly like the old ``print()``
calls were — while ALSO being written, with timestamps and levels, to a
rotating file on disk.

Logger hierarchy: every module logs under the "pwb" parent
(e.g. "pwb.discovery", "pwb.deploy"). Handlers are attached once to "pwb"
with propagation off, so messages are emitted exactly once.

Env vars:
  LOG_DIR        directory for log files       (default ./output/logs)
  LOG_LEVEL      console + file level           (default INFO)
  LOG_MAX_BYTES  rotate after N bytes           (default 5_000_000)
  LOG_BACKUPS    how many rotated files to keep (default 5)
"""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

ROOT_LOGGER_NAME = "pwb"

_configured = False


class _StdoutHandler(logging.Handler):
    """Write to whatever ``sys.stdout`` currently is, resolved at emit time so
    server.py's per-job stdout redirection still captures log output."""

    def emit(self, record):
        try:
            msg = self.format(record)
            stream = sys.stdout
            stream.write(msg + "\n")
            stream.flush()
        except RecursionError:  # pragma: no cover
            raise
        except Exception:
            self.handleError(record)


def log_path() -> Path:
    return Path(os.getenv("LOG_DIR", "./output/logs")) / "app.log"


def setup_logging() -> logging.Logger:
    """Idempotently configure the 'pwb' logger with a clean stdout handler and a
    rotating file handler. Safe to call multiple times (e.g. from both the
    server lifespan and __main__)."""
    global _configured
    logger = logging.getLogger(ROOT_LOGGER_NAME)
    if _configured:
        return logger

    level = getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO)
    logger.setLevel(level)
    logger.propagate = False  # don't double-emit through the root logger

    # Console / job-stream handler: bare message, so the dashboard log lines and
    # captured job logs look identical to the old print() output.
    console = _StdoutHandler()
    console.setLevel(level)
    console.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(console)

    # Rotating file handler: full context for after-the-fact debugging.
    try:
        path = log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            path,
            maxBytes=int(os.getenv("LOG_MAX_BYTES", "5000000")),
            backupCount=int(os.getenv("LOG_BACKUPS", "5")),
            encoding="utf-8",
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)-7s %(name)s %(message)s",
                              datefmt="%Y-%m-%d %H:%M:%S")
        )
        logger.addHandler(file_handler)
    except Exception as exc:  # never let logging setup crash the app
        logger.warning("[logging] file handler disabled (%s)", exc)

    _configured = True
    return logger


def get_logger(name: str) -> logging.Logger:
    """Return a child logger under the 'pwb' parent. Ensures setup has run so a
    standalone import (e.g. running discovery.py directly) still logs."""
    if not _configured:
        setup_logging()
    return logging.getLogger(f"{ROOT_LOGGER_NAME}.{name}")
