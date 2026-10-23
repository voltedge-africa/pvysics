from typing import TYPE_CHECKING

from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QMainWindow, QTabWidget

from pvysics.gui.dashboard import Dashboard
from pvysics.gui.model_view import ModelView
from pvysics.gui.process_view import ProcessView
from pvysics.gui.setup_view import SetupView
from pvysics.gui.theme import ThemeMenu
from pvysics.run import RunConfig

if TYPE_CHECKING:
    from pvysics.gui.session import Session


class MainWindow(QMainWindow):
    """The operator HMI window: a tab view of the Process, Model and Setup views on the session's run.

    The run, its history and the theme belong to the session. Apply on the Setup view starts a new
    run in the session, which resets every window. The HMI can be closed and shown again without
    stopping the run.
    """

    def __init__(self, session: "Session") -> None:
        super().__init__()
        self.setWindowTitle("PV Digital Twin")
        self.session = session
        self.theme = session.theme
        self.bus = session.bus
        self.history = session.history
        self.playback = session.playback
        self.process_view = ProcessView(self.playback, self.bus)
        self.model_view = ModelView(self.playback, self.bus, theme=self.theme)
        self.setup_view = SetupView(session.config)
        self.setup_view.apply_requested.connect(self._apply_setup)
        self._tabs = QTabWidget()
        self._tabs.addTab(self.process_view, "Process")
        self._tabs.addTab(self.model_view, "Model")
        self._tabs.addTab(self.setup_view, "Setup")
        self.setCentralWidget(self._tabs)

        window_menu = self.menuBar().addMenu("&Window")
        self.open_dashboard_action = QAction("Open Dashboard", self)
        self.open_dashboard_action.triggered.connect(self._on_open_dashboard_triggered)
        window_menu.addAction(self.open_dashboard_action)
        self.open_launcher_action = QAction("Open Launcher", self)
        self.open_launcher_action.triggered.connect(self._on_open_launcher_triggered)
        window_menu.addAction(self.open_launcher_action)
        ThemeMenu(self, self.theme)

    def _apply_setup(self, config: RunConfig) -> None:
        """Start a new run from config in the session. The Dashboard follows the new config too."""
        self.session.apply_config(config)
        self._tabs.setCurrentWidget(self.process_view)

    def _on_open_dashboard_triggered(self, *_args) -> None:
        self.open_dashboard()

    def _on_open_launcher_triggered(self, *_args) -> None:
        self.session.open_launcher()

    def open_dashboard(self) -> Dashboard:
        """Show the Dashboard, creating it on first use. Closing it leaves the HMI and the run running."""
        return self.session.open_dashboard()
