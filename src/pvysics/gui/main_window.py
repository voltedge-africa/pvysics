from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QMainWindow, QTabWidget

from pvysics.gui.dashboard import Dashboard
from pvysics.gui.data_bus import DataBus
from pvysics.gui.model_view import ModelView
from pvysics.gui.playback import PlaybackController
from pvysics.gui.process_view import ProcessView
from pvysics.gui.setup_view import SetupView
from pvysics.history import RunHistory
from pvysics.run import RunConfig, bundled_run_config


class MainWindow(QMainWindow):
    """The operator HMI window: a tab view of the Process, Model and Setup views on one run.

    The window keeps the run's history, fed from the bus, and opens the read-only Dashboard on it.
    Apply on the Setup view replaces the run through the playback controller.
    """

    def __init__(self, bus: DataBus | None = None, config: RunConfig | None = None) -> None:
        super().__init__()
        self.setWindowTitle("PV Digital Twin")
        self.bus = DataBus() if bus is None else bus  # owned by Python, so it outlives the playback timer
        config = bundled_run_config() if config is None else config
        self.history = RunHistory()
        self.bus.sample.connect(self.history.record_sample)
        self.bus.event.connect(self.history.record_event)
        self.bus.run_reset.connect(self.history.clear)
        self.playback = PlaybackController(config, self.bus, self)
        self.process_view = ProcessView(self.playback, self.bus)
        self.model_view = ModelView(self.playback, self.bus)
        self.setup_view = SetupView(config)
        self.setup_view.apply_requested.connect(self._apply_setup)
        self._tabs = QTabWidget()
        self._tabs.addTab(self.process_view, "Process")
        self._tabs.addTab(self.model_view, "Model")
        self._tabs.addTab(self.setup_view, "Setup")
        self.setCentralWidget(self._tabs)

        self._dashboard: Dashboard | None = None
        self.open_dashboard_action = QAction("Open Dashboard", self)
        self.open_dashboard_action.triggered.connect(self._on_open_dashboard_triggered)
        self.menuBar().addMenu("&Window").addAction(self.open_dashboard_action)

    def _apply_setup(self, config: RunConfig) -> None:
        """Start a new run from config. The bus resets the history and the views; the Dashboard takes the new limits."""
        self.playback.load(config)
        if self._dashboard is not None:
            self._dashboard.set_thresholds(config.thresholds)
        self.playback.start()
        self._tabs.setCurrentWidget(self.process_view)

    def _on_open_dashboard_triggered(self, *_args) -> None:
        self.open_dashboard()

    def open_dashboard(self) -> Dashboard:
        """Show the Dashboard, creating it on first use. Closing it leaves the HMI and the run running."""
        if self._dashboard is None:
            self._dashboard = Dashboard(
                self.history, self.bus, self.playback.config.thresholds, parent=self
            )
        self._dashboard.show()
        self._dashboard.raise_()
        self._dashboard.activateWindow()
        return self._dashboard
