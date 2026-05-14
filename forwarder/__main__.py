"""Entry point: `python -m forwarder`.

Starts the file-system watcher and a retry loop in a daemon thread.
"""

import logging
import threading

from . import retry, watcher
from .config import settings


def main() -> None:
    logging.basicConfig(
        level=settings.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    log = logging.getLogger("forwarder")
    log.info(
        "starting forwarder → %s (verify_ssl=%s)",
        settings.paperless_url,
        settings.paperless_verify_ssl,
    )

    threading.Thread(target=retry.run, name="retry", daemon=True).start()
    watcher.run()  # blocks


if __name__ == "__main__":
    main()
