"""Structured logging for Glitch Maker.

Logs to console + file. Crash logs are written next to the executable.
Usage:
    from utils.logger import log, get_logger
    log.info("Loaded file: %s", path)
    log.error("Effect failed: %s", ex)
"""
import logging
import logging.handlers
import os
import sys
import traceback
from datetime import datetime

LOG_FORMAT = "[%(asctime)s] %(levelname)-5s %(name)-18s │ %(message)s"
LOG_DATE = "%H:%M:%S"


def _get_log_dir():
    """Return the logs directory next to the executable or script."""
    if getattr(sys, 'frozen', False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(os.path.join(__file__, "..")))
    return os.path.join(base, "logs")


_LOG_DIR = _get_log_dir()
_LOG_FILE = os.path.join(_LOG_DIR, "glitchmaker.log")
_CRASH_FILE = os.path.join(_LOG_DIR, "crash.log")


def _setup_root():
    """Configure root logger with console + file handlers."""
    root = logging.getLogger("glitch")
    if root.handlers:
        return root
    root.setLevel(logging.DEBUG)

    # Console: INFO and above
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE))
    root.addHandler(ch)

    # File: DEBUG and above (rotating, 2MB max, 3 backups)
    try:
        os.makedirs(_LOG_DIR, exist_ok=True)
        fh = logging.handlers.RotatingFileHandler(
            _LOG_FILE, encoding="utf-8", maxBytes=2_000_000, backupCount=3)
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE))
        root.addHandler(fh)
    except Exception:
        pass  # Can't log to file — that's OK

    return root


def get_logger(name: str = "") -> logging.Logger:
    """Get a child logger under 'glitch' namespace."""
    _setup_root()
    if name:
        return logging.getLogger(f"glitch.{name}")
    return logging.getLogger("glitch")


def write_crash_log(exc_type, exc_value, exc_tb):
    """Write a detailed crash report to logs/crash.log.
    Called by the global exception hook in main.py."""
    try:
        os.makedirs(_LOG_DIR, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        tb_str = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))

        # Append to crash log
        with open(_CRASH_FILE, "a", encoding="utf-8") as f:
            f.write(f"\n{'='*60}\n")
            f.write(f"CRASH REPORT — {timestamp}\n")
            f.write(f"{'='*60}\n")
            f.write(tb_str)
            f.write(f"\nPython: {sys.version}\n")
            f.write(f"Platform: {sys.platform}\n")
            f.write(f"Frozen: {getattr(sys, 'frozen', False)}\n")
            f.write(f"{'='*60}\n\n")

        # Also log to main logger
        _setup_root()
        logging.getLogger("glitch.crash").critical(
            "Unhandled exception: %s: %s", exc_type.__name__, exc_value)

        return _CRASH_FILE
    except Exception:
        return None


# Convenience: default logger
log = get_logger()
