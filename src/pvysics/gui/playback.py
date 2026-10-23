"""Playback: replays a precomputed RunResult onto the DataBus in real time.

The clock is simulated time. Each tick adds speed / TICKS_PER_SECOND simulated seconds and
emits every Sample (and Event) that the clock has reached. Changing speed only changes the
rate, so a run is never restarted by a speed change.
"""

import numpy as np
from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from pvysics.gui.data_bus import DataBus
from pvysics.run import RunResult

TICKS_PER_SECOND = 30
SPEEDS = (1.0, 60.0, 600.0, 3600.0, 28800.0)  # 28800x plays a day in 3 s
DEFAULT_SPEED = SPEEDS[0]


def _seconds(delta: np.timedelta64) -> float:
    return float(delta / np.timedelta64(1, "s"))


class PlaybackController(QObject):
    """Plays a RunResult through a DataBus. Start, pause, reset and speed."""

    running_changed = pyqtSignal(bool)

    def __init__(self, result: RunResult, bus: DataBus, parent: QObject | None = None) -> None:
        super().__init__(parent)
        if not result.samples:
            raise ValueError("cannot play a run with no samples")
        self._result = result
        self._bus = bus
        origin = result.samples[0].timestamp
        self._sample_offsets = [_seconds(sample.timestamp - origin) for sample in result.samples]
        self._event_offsets = [_seconds(event.timestamp - origin) for event in result.events]
        self._speed = DEFAULT_SPEED
        self._clock_s = 0.0
        self._next_sample = 0
        self._next_event = 0
        self._running = False
        self._timer = QTimer(self)
        self._timer.setInterval(1000 // TICKS_PER_SECOND)
        self._timer.timeout.connect(self.tick)

    @property
    def result(self) -> RunResult:
        return self._result

    @property
    def speed(self) -> float:
        return self._speed

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def is_finished(self) -> bool:
        return self._next_sample >= len(self._sample_offsets)

    def set_speed(self, speed: float) -> None:
        if speed <= 0.0:
            raise ValueError("speed must be positive")
        self._speed = speed

    def start(self) -> None:
        if not self.is_finished:
            self._set_running(True)

    def pause(self) -> None:
        self._set_running(False)

    def reset(self) -> None:
        self._set_running(False)
        self._clock_s = 0.0
        self._next_sample = 0
        self._next_event = 0
        self._bus.run_reset.emit()

    def tick(self) -> None:
        """Advance the clock by one tick and emit everything it has reached."""
        if not self._running:
            return
        self._clock_s += self._speed / TICKS_PER_SECOND
        while not self.is_finished and self._sample_offsets[self._next_sample] <= self._clock_s:
            self._bus.sample.emit(self._result.samples[self._next_sample])
            self._next_sample += 1
        while (
            self._next_event < len(self._event_offsets)
            and self._event_offsets[self._next_event] <= self._clock_s
        ):
            self._bus.event.emit(self._result.events[self._next_event])
            self._next_event += 1
        if self.is_finished:
            self._set_running(False)

    def _set_running(self, running: bool) -> None:
        if running == self._running:
            return
        self._running = running
        if running:
            self._timer.start()
        else:
            self._timer.stop()
        self.running_changed.emit(running)
