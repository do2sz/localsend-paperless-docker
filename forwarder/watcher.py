"""Filesystem watcher that debounces newly-arrived files and forwards them
to Paperless. On failure, moves the file into the retry directory.
"""

import logging
import shutil
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from . import paperless
from .config import settings

log = logging.getLogger(__name__)


def _move_to_retry(file_path: Path, error: str) -> None:
    """Move a failed file into RETRY_DIR/<timestamp>/<filename> with a
    sidecar .err file describing the last error.
    """
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dst_dir = settings.retry_dir / stamp
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / file_path.name
    shutil.move(str(file_path), str(dst))
    (dst.with_suffix(dst.suffix + ".err")).write_text(error, encoding="utf-8")
    log.warning("moved to retry: %s (%s)", dst, error)


def _process(file_path: Path) -> None:
    """Forward a single stable file. Deletes on success, retries on failure."""
    if not file_path.is_file():
        return
    if file_path.suffix in (".part", ".tmp", ".crdownload"):
        log.debug("skipping partial file %s", file_path)
        return
    try:
        paperless.forward(file_path)
        try:
            file_path.unlink()
        except FileNotFoundError:
            pass
        log.info("forwarded and deleted: %s", file_path.name)
    except Exception as e:  # noqa: BLE001 - we want to catch everything here
        try:
            _move_to_retry(file_path, repr(e))
        except Exception:
            log.exception("could not move %s to retry", file_path)


def _wait_until_stable(file_path: Path, debounce: float) -> bool:
    """Wait until the file's size stops changing for `debounce` seconds.
    Returns True if the file became stable, False if it disappeared.
    """
    last_size = -1
    stable_since = 0.0
    while True:
        try:
            size = file_path.stat().st_size
        except FileNotFoundError:
            return False
        now = time.monotonic()
        if size != last_size:
            last_size = size
            stable_since = now
        elif size > 0 and now - stable_since >= debounce:
            return True
        time.sleep(max(0.2, debounce / 4))


class _Handler(FileSystemEventHandler):
    def __init__(self) -> None:
        self._scheduled: set[Path] = set()
        self._lock = threading.Lock()

    def _enqueue(self, path: Path) -> None:
        with self._lock:
            if path in self._scheduled:
                return
            self._scheduled.add(path)

        def run() -> None:
            try:
                if _wait_until_stable(path, settings.watcher_debounce_seconds):
                    _process(path)
            finally:
                with self._lock:
                    self._scheduled.discard(path)

        threading.Thread(target=run, daemon=True, name=f"fwd-{path.name}").start()

    def on_created(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        self._enqueue(Path(event.src_path))

    def on_moved(self, event: FileSystemEvent) -> None:
        # localsend-cli may rename a .part-style temp file → final name
        if event.is_directory:
            return
        self._enqueue(Path(event.dest_path))


def run() -> None:
    """Blocks forever, watching INCOMING_DIR."""
    settings.incoming_dir.mkdir(parents=True, exist_ok=True)

    # Pick up files that are already present at startup (e.g. left over from
    # a previous run that crashed between receive and forward).
    for existing in settings.incoming_dir.iterdir():
        if existing.is_file():
            log.info("startup: enqueueing pre-existing %s", existing.name)
            threading.Thread(
                target=lambda p=existing: (
                    _wait_until_stable(p, settings.watcher_debounce_seconds)
                    and _process(p)
                ),
                daemon=True,
            ).start()

    observer = Observer()
    observer.schedule(_Handler(), str(settings.incoming_dir), recursive=True)
    observer.start()
    log.info("watching %s", settings.incoming_dir)
    try:
        while True:
            time.sleep(3600)
    finally:
        observer.stop()
        observer.join()
