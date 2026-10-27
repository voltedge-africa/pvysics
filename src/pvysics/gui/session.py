"""The app session: the one run and the windows that show it.

The session owns the DataBus, the PlaybackController, the RunHistory, the current RunConfig (the
playback's config), the ThemeManager and the log (one LogModel fed by one LogBridge), so the run
belongs to the application and not to any window. The simple window, or in the advanced version the HMI, the Dashboard and the Sensors window, are created here on first use and kept by the
session. Opening a window that is open raises it. Closing a window only hides it, so it can be
shown again and the run goes on.
"""

import logging
from collections.abc import Callable

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QApplication, QMainWindow

from pvysics.dataset import DatasetReport, DatasetStore, default_store
from pvysics.gui.alarm_panel import AlarmMonitor
from pvysics.gui.dashboard import Dashboard
from pvysics.gui.data_bus import DataBus
from pvysics.gui.log_bridge import LogBridge
from pvysics.gui.main_window import MainWindow
from pvysics.gui.playback import PlaybackController
from pvysics.gui.sensors import SensorsWindow
from pvysics.gui.simple_window import SimpleWindow
from pvysics.gui.theme import ThemeManager, apply_palette
from pvysics.history import RunHistory
from pvysics.log_model import LogModel
from pvysics.run import RunConfig, bundled_run_config

HMI_KEY = "hmi"
DASHBOARD_KEY = "dashboard"
SENSORS_KEY = "sensors"
SIMPLE_KEY = "simple"
log = logging.getLogger(__name__)


class Session(QObject):
    """The app-level run, dataset store and theme, shared by every window the session opens."""

    config_changed = pyqtSignal(object)  # RunConfig, once a new config has been applied
    dataset_replayed = pyqtSignal(str)  # the name of the dataset whose Samples were replayed

    def __init__(
        self,
        config: RunConfig | None = None,
        theme: ThemeManager | None = None,
        parent: QObject | None = None,
    ) -> None:
        # Owned by the application, so the run and its windows live until the event loop ends and
        # are not freed by Python's garbage collector while a timer or a window still refers to them.
        super().__init__(QApplication.instance() if parent is None else parent)
        self.theme = ThemeManager(parent=self) if theme is None else theme
        self.theme.changed.connect(apply_palette)
        apply_palette(self.theme.palette)
        self.bus = DataBus()  # owned here, so it outlives the windows and the playback timer
        self.history = RunHistory()
        self.bus.sample.connect(self.history.record_sample)
        self.bus.event.connect(self.history.record_event)
        self.bus.run_reset.connect(self.history.clear)
        self.alarms = AlarmMonitor(self.bus, self)  # alarms are recorded and logged whichever windows are open
        self.log_model = LogModel()
        self.log_bridge = LogBridge(self.log_model, self)  # from now on, "pvysics" records reach the model
        self.datasets = default_store()  # the datasets the user imported
        config = bundled_run_config() if config is None else config
        self.playback = PlaybackController(config, self.bus, self)
        self._windows: dict[str, QMainWindow] = {}

    def close(self) -> None:
        """Detach the log handler. The session still works afterwards, but its log stops updating."""
        self.log_bridge.close()

    @property
    def config(self) -> RunConfig:
        return self.playback.config

    @property
    def hmi(self) -> MainWindow | None:
        return self._windows.get(HMI_KEY)

    @property
    def dashboard(self) -> Dashboard | None:
        return self._windows.get(DASHBOARD_KEY)

    @property
    def hmi_open(self) -> bool:
        """True while the HMI is shown. A window that was closed is not open."""
        hmi = self.hmi
        return hmi is not None and hmi.isVisible()

    def apply_config(self, config: RunConfig) -> None:
        """Start a new run from config. The history and every window reset and follow the new config."""
        self.playback.load(config)  # checks the config before anything changes
        self.config_changed.emit(config)
        self.playback.start()

    def replay_dataset(self, report: DatasetReport) -> None:
        """Show a dataset's analysed Samples as the run: the live run pauses and the history is replaced.

        The samples go through the data bus as Samples, so every window (Dashboard, Trends,
        Data, Event Log) reads them as it reads a run. A dataset has no Events.
        """
        self.playback.pause()
        self.bus.run_reset.emit()
        for sample in report.samples:
            self.bus.sample.emit(sample)
        log.info("Dataset replayed: %s (%d samples)", report.name, len(report.samples))
        self.dataset_replayed.emit(report.name)

    def open_simple(self) -> SimpleWindow:
        return self._open(SIMPLE_KEY, SimpleWindow)

    def open_hmi(self) -> MainWindow:
        return self._open(HMI_KEY, MainWindow)

    def open_dashboard(self) -> Dashboard:
        return self._open(DASHBOARD_KEY, Dashboard)

    def open_sensors(self) -> SensorsWindow:
        return self._open(SENSORS_KEY, SensorsWindow)

    def _open(self, key: str, make: Callable[["Session"], QMainWindow]) -> QMainWindow:
        window = self._windows.get(key)
        if window is None:
            window = make(self)
            self._windows[key] = window
        log.debug("Window shown: %s", key)
        window.show()
        window.raise_()
        window.activateWindow()
        return window
