# SPDX-License-Identifier: MIT

import collections
import logging
import os
import sys


_configured = False

# Ring buffer that keeps the most recent log records in memory.
# Used by the excepthook to show context leading up to a crash.
_BUFFER_SIZE = 200


class RecentLogHandler(logging.Handler):
    """A handler that stores the last *maxlen* formatted log records in memory."""

    def __init__(self, maxlen=_BUFFER_SIZE):
        super().__init__()
        self.records = collections.deque(maxlen=maxlen)

    def emit(self, record):
        self.records.append(self.format(record))

    def get_recent(self, n=None):
        """Return the last *n* formatted log lines (all if *n* is None)."""
        if n is None:
            return list(self.records)
        return list(self.records)[-n:]


# Module-level reference so the excepthook can access it.
_recent_handler = None


def get_recent_log(n=50):
    """Return the last *n* log lines from the in-memory buffer.

    Returns an empty list if logging has not been configured yet.
    """
    if _recent_handler is None:
        return []
    return _recent_handler.get_recent(n)


def setup_logging(level=None):
    """Configure the root ``dioptas`` logger.

    Call this once at application startup (before any model or controller code
    runs).  It is safe to call more than once -- subsequent calls are no-ops.

    By default only a console handler (stderr, WARNING level) and an in-memory
    ring buffer (DEBUG level, last 200 entries) are created.  The ring buffer
    is used by the exception dialog to show what happened before a crash.

    Set the *DIOPTAS_LOG_LEVEL* environment variable to ``DEBUG`` or ``INFO``
    to see more output on the console.  Set *DIOPTAS_LOG_FILE* to a path to
    additionally write all log output to a file.

    Parameters
    ----------
    level : int or str, optional
        Logging level for the console handler.  Defaults to ``WARNING``.
    """
    global _configured, _recent_handler
    if _configured:
        return
    _configured = True

    if level is None:
        level = os.environ.get("DIOPTAS_LOG_LEVEL", "WARNING")

    root = logging.getLogger("dioptas")
    root.setLevel(logging.DEBUG)  # capture everything; handlers decide output

    fmt = logging.Formatter(
        "%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # --- Console handler (stderr) ---
    console = logging.StreamHandler(sys.stderr)
    console.setLevel(level)
    console.setFormatter(fmt)
    root.addHandler(console)

    # --- In-memory ring buffer (always captures DEBUG) ---
    _recent_handler = RecentLogHandler(maxlen=_BUFFER_SIZE)
    _recent_handler.setLevel(logging.DEBUG)
    _recent_handler.setFormatter(fmt)
    root.addHandler(_recent_handler)

    # --- Optional file handler (opt-in via DIOPTAS_LOG_FILE) ---
    log_file = os.environ.get("DIOPTAS_LOG_FILE")
    if log_file:
        try:
            from logging.handlers import RotatingFileHandler

            os.makedirs(os.path.dirname(log_file) or ".", exist_ok=True)
            file_handler = RotatingFileHandler(
                log_file, maxBytes=5 * 1024 * 1024, backupCount=3
            )
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(fmt)
            root.addHandler(file_handler)
        except OSError:
            root.warning("Could not open log file %s for writing", log_file)
