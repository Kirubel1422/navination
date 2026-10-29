"""Background refresh of the open data: on start (if stale) and then every day.

Runs in a daemon thread so the API serves immediately from the bundled or last synced copies.
"""

import logging
import threading

from app.agent.ajman import AjmanData
from app.agent.bayanat import Bayanat
from app.core.config import get_settings
from app.db.session import get_sessionmaker
from app.opendata import insights, sync

logger = logging.getLogger("navination.opendata")
_started = threading.Event()


def refresh_if_stale() -> None:
    settings = get_settings()
    with get_sessionmaker()() as db:
        sync.import_bundled(db)
        insights.invalidate()
        if not sync.is_stale(db, settings.open_data_max_age_hours):
            return
        timeout = settings.web_fetch_timeout_seconds * 3
        sync.run_sync(db, Bayanat(timeout), AjmanData(timeout))
    insights.invalidate()


def _loop(stop: threading.Event) -> None:
    hours = get_settings().open_data_max_age_hours
    while not stop.is_set():
        try:
            refresh_if_stale()
        except Exception:  # noqa: BLE001 - a failed refresh keeps the previous data
            logger.exception("open data refresh failed; serving the previous copies")
        stop.wait(max(hours, 1) * 3600)


def start(stop: threading.Event) -> None:
    if _started.is_set():
        return
    _started.set()
    threading.Thread(target=_loop, args=(stop,), name="open-data-sync", daemon=True).start()
