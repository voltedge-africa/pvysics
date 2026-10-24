import logging
from typing import TYPE_CHECKING

from PyQt6.QtGui import QAction
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDockWidget, QMainWindow, QTabWidget, QWidget

from pvysics.gui.dashboard import Dashboard
from pvysics.gui.log_pane import bottom_log_pane
from pvysics.gui.model_view import ModelView
from pvysics.gui.process_view import ProcessView
from pvysics.gui.setup_view import SetupView
from pvysics.gui.theme import ThemeMenu
from pvysics.run import RunConfig

log = logging.getLogger(__name__)
DEFAULT_WIDTH_PX = 1280
DEFAULT_HEIGHT_PX = 800
ALARMS_WIDTH_PX = 300

if TYPE_CHECKING:
    from pvysics.gui.session import Session


class MainWindow(QMainWindow):
    """The operator HMI window: the Process, Model and Setup views as tabs on the session's run.

    The alarm list is a dock on the right and the log a dock along the bottom: drag, float or close either,
    and bring it back from View > Panels.

    The run, its history and the theme belong to the session. Apply on the Setup view starts a new
    run in the session, which resets every window. The HMI can be closed and shown again without
    stopping the run.
    """

    def __init__(self, session: "Session") -> None:
        super().__init__()
        self.setWindowTitle("PV Digital Twin")
        self.resize(DEFAULT_WIDTH_PX, DEFAULT_HEIGHT_PX)
        self.session = session
        self.theme = session.theme
        self.bus = session.bus
        self.history = session.history
        self.playback = session.playback
        self.process_view = ProcessView(self.playback, self.bus, theme=self.theme, history=self.history)
        self.model_view = ModelView(self.playback, self.bus, theme=self.theme)
        self.setup_view = SetupView(session.config, self.theme)
        self.setup_view.apply_requested.connect(self._apply_setup)
        self._tabs = QTabWidget()
        self._tabs.addTab(self.process_view, "Process")
        self._tabs.addTab(self.model_view, "Model")
        self._tabs.addTab(self.setup_view, "Setup")
        self.setCentralWidget(self._tabs)
        self.log_pane = bottom_log_pane(self, session.log_bridge, self.theme)
        self.docks = {"alarms": _dock("Alarms", self.process_view.alarm_panel)}
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.docks["alarms"])
        self.resizeDocks([self.docks["alarms"]], [ALARMS_WIDTH_PX], Qt.Orientation.Horizontal)

        window_menu = self.menuBar().addMenu("&Window")
        self.open_dashboard_action = QAction("Open Dashboard", self)
        self.open_dashboard_action.triggered.connect(self._on_open_dashboard_triggered)
        window_menu.addAction(self.open_dashboard_action)
        self.theme_menu = ThemeMenu(self, self.theme)
        self.theme_menu.add_action(self.log_pane.view_action)
        self.theme_menu.add_actions([dock.toggleViewAction() for dock in self.docks.values()], "Panels")

    def closeEvent(self, event) -> None:
        log.debug("Window closed: HMI")
        self.setup_view.shutdown()  # a running fetch ends before the window closes
        super().closeEvent(event)

    def _apply_setup(self, config: RunConfig) -> None:
        """Start a new run from config in the session. The Dashboard follows the new config too."""
        self.session.apply_config(config)
        self.show_view(self.process_view)

    def show_view(self, view: QWidget) -> None:
        """Bring a view (Process, Model or Setup) to the front."""
        self._tabs.setCurrentWidget(view)

    def current_view(self) -> QWidget:
        """The view at the front: Process, Model or Setup."""
        return self._tabs.currentWidget()

    def _on_open_dashboard_triggered(self, *_args) -> None:
        self.open_dashboard()


    def open_dashboard(self) -> Dashboard:
        """Show the Dashboard, creating it on first use. Closing it leaves the HMI and the run running."""
        return self.session.open_dashboard()


def _dock(title: str, widget: QWidget) -> QDockWidget:
    dock = QDockWidget(title)
    dock.setObjectName(f"dock_{title}")
    dock.setWidget(widget)
    return dock
