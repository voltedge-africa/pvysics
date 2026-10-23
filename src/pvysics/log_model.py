"""The log model: a bounded buffer of log entries with a level threshold. Headless, no Qt.

The app's logging handler (gui/log_bridge.py) turns each record into a LogEntry and appends it here
on the UI thread. Both windows' panes show this one model. A threshold hides lower-level entries
without deleting them, so raising it and lowering it again shows them all once more.
"""

import logging
import time
from collections import deque
from dataclasses import dataclass

DEFAULT_CAPACITY = 2000
DEFAULT_THRESHOLD = logging.INFO


@dataclass(frozen=True)
class LogEntry:
    timestamp: float  # seconds since the epoch, as logging records give it
    level: int  # a logging level, such as logging.WARNING
    logger: str  # the logger name, such as "pvysics.gui.session"
    message: str

    @property
    def level_name(self) -> str:
        return logging.getLevelName(self.level)


def entry_from_record(record: logging.LogRecord) -> LogEntry:
    return LogEntry(
        timestamp=record.created,
        level=record.levelno,
        logger=record.name,
        message=record.getMessage(),
    )


def format_entry(entry: LogEntry) -> str:
    """One line: HH:MM:SS, the level, then the message. A message's own line breaks become spaces."""
    stamp = time.strftime("%H:%M:%S", time.localtime(entry.timestamp))
    message = " ".join(entry.message.splitlines())
    return f"{stamp} {entry.level_name:<7} {message}"


class LogModel:
    """The newest `capacity` entries, oldest dropped first, shown at or above `threshold`."""

    def __init__(self, capacity: int = DEFAULT_CAPACITY) -> None:
        if capacity < 1:
            raise ValueError("capacity must be at least 1")
        self._entries: deque[LogEntry] = deque(maxlen=capacity)
        self._threshold = DEFAULT_THRESHOLD

    @property
    def capacity(self) -> int:
        return self._entries.maxlen

    @property
    def threshold(self) -> int:
        return self._threshold

    def __len__(self) -> int:
        return len(self._entries)

    def append(self, entry: LogEntry) -> None:
        self._entries.append(entry)

    def set_threshold(self, level: int) -> None:
        """Show entries at this level and above. Hidden entries are kept."""
        self._threshold = level

    def clear(self) -> None:
        self._entries.clear()

    def visible(self) -> tuple[LogEntry, ...]:
        """The entries at or above the threshold, oldest first."""
        return tuple(entry for entry in self._entries if entry.level >= self._threshold)

    def as_text(self) -> str:
        """The visible entries, one per line."""
        return "\n".join(format_entry(entry) for entry in self.visible())
