"""Periodic retry loop: re-attempts forwarding of files in RETRY_DIR.

Layout in RETRY_DIR:
    <timestamp>/<filename>
    <timestamp>/<filename>.err   (sidecar with last error message)
"""

import logging
import time
from pathlib import Path

from . import paperless
from .config import settings

log = logging.getLogger(__name__)


def _retry_once(file_path: Path) -> None:
    err_file = file_path.with_suffix(file_path.suffix + ".err")
    try:
        paperless.forward(file_path)
    except Exception as e:  # noqa: BLE001
        log.warning("retry failed for %s: %s", file_path.name, e)
        try:
            err_file.write_text(repr(e), encoding="utf-8")
        except Exception:
            pass
        return

    log.info("retry succeeded for %s", file_path.name)
    try:
        file_path.unlink()
    except FileNotFoundError:
        pass
    if err_file.exists():
        err_file.unlink()
    # Clean up empty timestamp folder
    parent = file_path.parent
    try:
        if parent != settings.retry_dir and not any(parent.iterdir()):
            parent.rmdir()
    except OSError:
        pass


def _scan() -> None:
    if not settings.retry_dir.exists():
        return
    for path in sorted(settings.retry_dir.rglob("*")):
        if path.is_file() and path.suffix != ".err":
            _retry_once(path)


def run() -> None:
    """Blocks forever, rescanning RETRY_DIR every retry_interval_seconds."""
    log.info("retry loop active (interval=%ss)", settings.retry_interval_seconds)
    while True:
        try:
            _scan()
        except Exception:
            log.exception("retry scan crashed")
        time.sleep(settings.retry_interval_seconds)
