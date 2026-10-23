"""The log bridge: one logging handler that feeds the session's LogModel on the UI thread.

Records can come from worker threads (validation now, a fetch later). The handler only emits a Qt
signal. Qt queues that signal to the thread the bridge lives in, so the model is changed and the
panes are updated on the UI thread only. attach() adds the handler to the "pvysics" logger and
sets that logger to DEBUG, so the panes can filter; close() removes the handler and restores the
logger's level. The session attaches one bridge and closes it on teardown.
"""

import logging

from PyQt6.QtCore import QObject, pyqtSignal

from pvysics.log_model import LogEntry, LogModel, entry_from_record

LOGGER_NAME = "pvysics"


class _SignalHandler(logging.Handler):
    """Hands each record to a deliver function. It runs on whichever thread logged the record."""

    def __init__(self, deliver) -> None:
        super().__init__(level=logging.DEBUG)
        self._deliver = deliver

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self._deliver(entry_from_record(record))
        except Exception:  # a bad record must not stop the caller; logging reports it instead
            self.handleError(record)


class LogBridge(QObject):
    """Feeds the shared LogModel. `updated` is emitted on the UI thread after the model changes."""

    updated = pyqtSignal()
    _delivered = pyqtSignal(object)  # LogEntry, emitted from any thread

    def __init__(self, model: LogModel, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.model = model
        self._delivered.connect(self._append)  # queued: _append always runs on the UI thread
        self._handler = _SignalHandler(self._delivered.emit)
        self._logger = logging.getLogger(LOGGER_NAME)
        self._previous_level = self._logger.level
        self._logger.setLevel(logging.DEBUG)
        self._logger.addHandler(self._handler)
        self._closed = False

    @property
    def closed(self) -> bool:
        return self._closed

    def set_threshold(self, level: int) -> None:
        """The level filter for every pane. Hidden entries stay in the model."""
        self.model.set_threshold(level)
        self.updated.emit()

    def clear(self) -> None:
        self.model.clear()
        self.updated.emit()

    def close(self) -> None:
        """Remove the handler, so no record reaches this model again. Safe to call twice."""
        if self._closed:
            return
        self._closed = True
        self._logger.removeHandler(self._handler)
        self._handler.close()
        self._logger.setLevel(self._previous_level)

    def _append(self, entry: LogEntry) -> None:
        self.model.append(entry)
        self.updated.emit()
