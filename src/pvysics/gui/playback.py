"""Playback: steps a Simulation onto the DataBus in real time, computing each Sample as it is shown.

The clock is simulated time. Each tick adds speed / TICKS_PER_SECOND simulated seconds and
computes and emits every Sample (and Event) that the clock has reached. Changing speed only
changes the rate, so a run is never restarted by a speed change. Faults can be injected or
cleared while the run plays; they apply from the next Sample.
"""

import logging

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from pvysics.faults import Fault
from pvysics.gui.data_bus import DataBus
from pvysics.run import RunConfig, Simulation

TICKS_PER_SECOND = 30
SPEEDS = (1.0, 60.0, 600.0, 3600.0, 28800.0)  # 28800x plays a day in 3 s
DEFAULT_SPEED = SPEEDS[0]
log = logging.getLogger(__name__)


class PlaybackController(QObject):
    """Plays a run through a DataBus. Start, pause, reset, speed and fault injection."""

    running_changed = pyqtSignal(bool)

    def __init__(self, config: RunConfig, bus: DataBus, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._config = config
        self._bus = bus
        self._simulation = Simulation(config)
        self._speed = DEFAULT_SPEED
        self._clock_s = 0.0
        self._running = False
        self._timer = QTimer(self)
        self._timer.setInterval(1000 // TICKS_PER_SECOND)
        self._timer.timeout.connect(self.tick)

    @property
    def config(self) -> RunConfig:
        return self._config

    @property
    def speed(self) -> float:
        return self._speed

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def is_finished(self) -> bool:
        return self._simulation.finished

    def set_speed(self, speed: float) -> None:
        if speed <= 0.0:
            raise ValueError("speed must be positive")
        self._speed = speed
        log.info("Speed set to %gx", speed)

    def inject(self, fault: Fault) -> None:
        """Make the fault active from the next Sample."""
        self._simulation.inject(fault)
        log.info("Fault injected: %s (severity %g)", fault.kind.value, fault.severity)
        self._emit_events()

    def clear_faults(self) -> None:
        """Clear all faults, live and scheduled, from the next Sample."""
        self._simulation.clear_faults()
        log.info("Faults cleared")
        self._emit_events()

    def start(self) -> None:
        if self.is_finished:
            return
        if not self._running:
            log.info("Run started")
        self._set_running(True)

    def pause(self) -> None:
        if self._running:
            log.info("Run paused")
        self._set_running(False)

    def load(self, config: RunConfig) -> None:
        """Replace the run with a new one from config. It starts paused, at its first Sample."""
        simulation = Simulation(config)  # checks the config before anything changes
        self._set_running(False)
        self._config = config
        self._simulation = simulation
        self._clock_s = 0.0
        self._bus.run_reset.emit()

    def reset(self) -> None:
        """Start the current run again from its first Sample, with its faults cleared."""
        log.info("Run reset to the start")
        self.load(self._config)

    def tick(self) -> None:
        """Advance the clock by one tick and emit everything it has reached."""
        if not self._running:
            return
        self._clock_s += self._speed / TICKS_PER_SECOND
        while not self.is_finished and self._simulation.next_offset_s <= self._clock_s:
            self._bus.sample.emit(self._simulation.step())
            self._emit_events()
        if self.is_finished:
            log.info("Run finished")
            self._set_running(False)

    def _emit_events(self) -> None:
        for event in self._simulation.drain_events():
            if event.kind == "state":
                log.info("State changed: %s", event.detail)
            else:
                log.debug("Fault changed: %s", event.detail)
            self._bus.event.emit(event)

    def _set_running(self, running: bool) -> None:
        if running == self._running:
            return
        self._running = running
        if running:
            self._timer.start()
        else:
            self._timer.stop()
        self.running_changed.emit(running)
