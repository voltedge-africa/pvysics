"""The live feed in the app: a server that takes readings, and the DataBus they are sent onto.

The LiveController owns the LiveServer and a LiveScorer. A device's POST arrives on a server thread; the
controller checks and scores it there, under a lock so readings keep their order, and hands each Sample to the
GUI thread by a queued signal, which puts it on the bus as a run's Sample. Every window then shows it as it shows
a run. The controller also watches for silence: if nothing arrives for the timeout, the feed's status says so.
Its settings (port, token, timeout, who may connect) persist like the theme.
"""

import logging
import secrets
import threading
import time
from collections.abc import Callable
from enum import Enum

from PyQt6.QtCore import QObject, QSettings, QTimer, pyqtSignal

from pvysics.gui.data_bus import DataBus
from pvysics.gui.theme import default_settings
from pvysics.live import LiveLog, LiveScorer, ReadingError, default_live_dir, now_stamp, parse_reading
from pvysics.live_server import IngestResult, LiveServer
from pvysics.run import RunConfig

log = logging.getLogger(__name__)
DEFAULT_PORT = 8765
DEFAULT_TIMEOUT_S = 30
MIN_TIMEOUT_S = 5
MAX_TIMEOUT_S = 3600
SILENCE_CHECK_MS = 1000
LOCAL_HOST = "127.0.0.1"
NETWORK_HOST = "0.0.0.0"
PORT_KEY, TOKEN_KEY, TIMEOUT_KEY, NETWORK_KEY = "live/port", "live/token", "live/timeout_s", "live/network"


class FeedStatus(Enum):
    STOPPED = "Stopped"
    WAITING = "Waiting for the first reading"
    RECEIVING = "Receiving"
    NO_DATA = "No data"


class LiveController(QObject):
    """Starts and stops the feed, scores what arrives and says how the feed is doing."""

    active_changed = pyqtSignal(bool)  # the feed started or stopped
    status_changed = pyqtSignal(object)  # a FeedStatus
    counts_changed = pyqtSignal()  # a reading was accepted or refused
    _scored = pyqtSignal(object, object)  # Sample, list of Events: from the server thread to the GUI thread

    def __init__(
        self,
        bus: DataBus,
        config_provider: Callable[[], RunConfig],
        settings: QSettings | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._bus = bus
        self._config_provider = config_provider
        self._settings = default_settings() if settings is None else settings
        self._lock = threading.Lock()
        self._server: LiveServer | None = None
        self._scorer: LiveScorer | None = None
        self._live_log: LiveLog | None = None
        self._status = FeedStatus.STOPPED
        self._last_arrival = 0.0
        self.accepted = 0
        self.rejected = 0
        self.last_error = ""
        self.last_reading_text = ""
        self.log_path = ""
        self._scored.connect(self._on_scored)
        bus.run_reset.connect(self._on_run_reset)
        self._timer = QTimer(self)
        self._timer.setInterval(SILENCE_CHECK_MS)
        self._timer.timeout.connect(self._check_silence)

        self.port = int(self._settings.value(PORT_KEY, DEFAULT_PORT, type=int))
        self.timeout_s = int(self._settings.value(TIMEOUT_KEY, DEFAULT_TIMEOUT_S, type=int))
        self.accept_network = bool(self._settings.value(NETWORK_KEY, True, type=bool))
        # A token made here is kept once the feed starts with it, so opening the app writes no settings.
        self.token = str(self._settings.value(TOKEN_KEY, "", type=str)) or secrets.token_urlsafe(16)

    @property
    def is_active(self) -> bool:
        return self._server is not None

    @property
    def has_data(self) -> bool:
        """True when a feed that has stopped left readings in the run, until the run is reset."""
        return not self.is_active and self.accepted > 0

    @property
    def status(self) -> FeedStatus:
        return self._status

    @property
    def listening_port(self) -> int:
        return self.port if self._server is None else self._server.port

    def configure(self, port: int, timeout_s: int, accept_network: bool) -> None:
        """Set and remember the port, the silence timeout and whether other devices may connect."""
        if not 0 <= port <= 65535:
            raise ValueError("the port must be between 0 and 65535")
        self.port = port
        self.timeout_s = max(MIN_TIMEOUT_S, min(MAX_TIMEOUT_S, int(timeout_s)))
        self.accept_network = accept_network
        self._settings.setValue(PORT_KEY, self.port)
        self._settings.setValue(TIMEOUT_KEY, self.timeout_s)
        self._settings.setValue(NETWORK_KEY, self.accept_network)

    def new_token(self) -> str:
        """Replace the token. A running feed keeps the old one until it is restarted."""
        self.token = secrets.token_urlsafe(16)
        self._settings.setValue(TOKEN_KEY, self.token)
        return self.token

    def start(self) -> None:
        """Start listening, with a new run: the history and the alarms are cleared. Raises OSError if the port is taken."""
        self.stop()
        self._settings.setValue(TOKEN_KEY, self.token)
        server = LiveServer(self._ingest, self.token, NETWORK_HOST if self.accept_network else LOCAL_HOST, self.port)
        server.start()  # may raise OSError: nothing has changed yet
        self._server = server
        with self._lock:
            self._scorer = LiveScorer(self._config_provider())
            self._live_log = self._open_log()
        self.accepted = self.rejected = 0
        self.last_error = self.last_reading_text = ""
        self._bus.run_reset.emit()
        self._timer.start()
        self.active_changed.emit(True)
        self._set_status(FeedStatus.WAITING)
        self.counts_changed.emit()
        log.info("Live feed started on port %d; readings are kept in %s", server.port, self.log_path)

    def stop(self) -> None:
        """Stop listening. What was received stays in the run and in the log file."""
        server = self._server
        if server is None:
            return
        self._server = None
        self._timer.stop()
        server.stop()
        with self._lock:
            if self._live_log is not None:
                self._live_log.close()
            self._live_log = None
            self._scorer = None
        self.active_changed.emit(False)
        self._set_status(FeedStatus.STOPPED)
        log.info("Live feed stopped after %d readings", self.accepted)

    def _open_log(self) -> LiveLog | None:
        try:
            live_log = LiveLog(default_live_dir())
        except OSError as error:
            log.warning("Live readings will not be kept in a file: %s", error)
            self.log_path = ""
            return None
        self.log_path = str(live_log.path)
        return live_log

    # The server thread

    def _ingest(self, body: object) -> IngestResult:
        """Check and score a decoded body, one reading or a list. Runs on a server thread."""
        items = body if isinstance(body, list) else [body]
        accepted = 0
        errors: list[str] = []
        with self._lock:
            scorer = self._scorer
            if scorer is None:
                return IngestResult(0, ("the feed is stopped",))
            for number, item in enumerate(items, start=1):
                try:
                    reading = parse_reading(item, received_at=now_stamp())
                    sample, events = scorer.score(reading)
                except ReadingError as error:
                    errors.append(f"reading {number}: {error}" if len(items) > 1 else str(error))
                    continue
                if self._live_log is not None:
                    self._live_log.append(reading)
                accepted += 1
                self._scored.emit(sample, events)  # queued: the GUI thread takes it in order
            self.accepted += accepted
            self.rejected += len(errors)
            if errors:
                self.last_error = errors[-1]
        self.counts_changed.emit()  # queued to the windows, which live on the GUI thread
        return IngestResult(accepted, tuple(errors))

    # The GUI thread

    def _on_scored(self, sample, events) -> None:
        if not self.is_active:
            return  # a reading that was in flight when the feed stopped
        self._bus.sample.emit(sample)
        for event in events:
            log.info("State changed: %s", event.detail)
            self._bus.event.emit(event)
        self._last_arrival = time.monotonic()
        self.last_reading_text = str(sample.timestamp).replace("T", " ")
        if self._status is not FeedStatus.RECEIVING:
            if self._status is FeedStatus.NO_DATA:
                log.info("Live feed: readings resumed")
            self._set_status(FeedStatus.RECEIVING)

    def _on_run_reset(self) -> None:
        """The run was reset by something other than the feed: its readings are gone, so are the counts."""
        if not self.is_active and (self.accepted or self.rejected):
            self.accepted = self.rejected = 0
            self.counts_changed.emit()

    def _check_silence(self) -> None:
        if self._status is not FeedStatus.RECEIVING:
            return
        if time.monotonic() - self._last_arrival > self.timeout_s:
            log.warning("Live feed: no reading for %d s", self.timeout_s)
            self._set_status(FeedStatus.NO_DATA)

    def _set_status(self, status: FeedStatus) -> None:
        if status is not self._status:
            self._status = status
            self.status_changed.emit(status)
