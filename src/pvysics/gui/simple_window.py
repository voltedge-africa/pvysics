"""The simple window: the whole app in one window, which is what opens unless PVYSICS_ADVANCED_VERSION is set.

A sidebar lists the pages (Dashboard, Analysis, SDM Model, Trends, Data, Event Log, Settings) and a stack shows
the chosen one. The Hide button hides the sidebar so a page has the whole window; a rail button, View > Sidebar (Ctrl+B) or Esc brings it back. The log is a pop-up
(View > Logs, Ctrl+L), as in the advanced version. The look is gui/simple_style.py, in the theme the user chose.

The pages are in gui/simple_pages.py. Everything is a view on the session's one run; the window adds navigation.
"""

import logging
from typing import TYPE_CHECKING

from PyQt6.QtGui import QAction, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from pvysics.gui.log_pane import popup_log_pane
from pvysics.gui.palette import Palette
from pvysics.gui.simple_pages import (
    AnalysisPage,
    DashboardPage,
    DataPage,
    EventLogPage,
    ModelPage,
    SettingsPage,
    TrendsPage,
)
from pvysics.gui.simple_style import simple_stylesheet
from pvysics.gui.theme import ThemeMenu
from pvysics.gui.ui_helpers import role_label
from pvysics.run import RunConfig

if TYPE_CHECKING:
    from pvysics.gui.session import Session

log = logging.getLogger(__name__)
DEFAULT_WIDTH_PX = 1400
DEFAULT_HEIGHT_PX = 860
SIDEBAR_WIDTH_PX = 230
RAIL_WIDTH_PX = 52
DASHBOARD = "Dashboard"
ANALYSIS = "Analysis"
SDM_MODEL = "SDM Model"
TRENDS = "Trends"
DATA = "Data"
EVENT_LOG = "Event Log"
SETTINGS = "Settings"
PAGE_NAMES = (DASHBOARD, ANALYSIS, SDM_MODEL, TRENDS, DATA, EVENT_LOG, SETTINGS)


class SimpleWindow(QMainWindow):
    """One window on the session's run: a sidebar of pages, and the page in front."""

    def __init__(self, session: "Session") -> None:
        super().__init__()
        self.setWindowTitle("PV Digital Twin")
        self.resize(DEFAULT_WIDTH_PX, DEFAULT_HEIGHT_PX)
        self.session = session
        self.theme = session.theme
        self.playback = session.playback

        self.dashboard_page = DashboardPage(session)
        self.analysis_page = AnalysisPage(session)
        self.model_page = ModelPage(session)
        self.trends_page = TrendsPage(session)
        self.data_page = DataPage(session)
        self.event_log_page = EventLogPage(session)
        self.settings_page = SettingsPage(session)
        self.pages = {
            DASHBOARD: self.dashboard_page,
            ANALYSIS: self.analysis_page,
            SDM_MODEL: self.model_page,
            TRENDS: self.trends_page,
            DATA: self.data_page,
            EVENT_LOG: self.event_log_page,
            SETTINGS: self.settings_page,
        }
        self.stack = QStackedWidget()
        for page in self.pages.values():
            self.stack.addWidget(page)

        self.nav_buttons: dict[str, QPushButton] = {}
        nav_group = QButtonGroup(self)
        nav_group.setExclusive(True)
        self.sidebar = QFrame()
        self.sidebar.setObjectName("simpleSidebar")
        self.sidebar.setFixedWidth(SIDEBAR_WIDTH_PX)
        side = QVBoxLayout(self.sidebar)
        side.setContentsMargins(14, 18, 14, 18)
        side.setSpacing(4)
        side.addWidget(role_label("PV DIGITAL TWIN", "brand"))
        side.addWidget(role_label("Physics-Informed\nState Estimation", "brandSub"))
        side.addSpacing(22)
        for name in PAGE_NAMES:
            button = QPushButton(name)
            button.setProperty("nav", "true")
            button.setCheckable(True)
            button.clicked.connect(self._on_nav_clicked)
            nav_group.addButton(button)
            side.addWidget(button)
            self.nav_buttons[name] = button
        side.addStretch(1)
        self.hide_button = QPushButton("⊗  HIDE")
        self.hide_button.setProperty("nav", "true")
        self.hide_button.setCheckable(True)
        self.hide_button.setToolTip("Hide the sidebar so the page has the whole window. Ctrl+B or Esc brings it back.")
        self.hide_button.toggled.connect(self._on_hide_toggled)
        side.addWidget(self.hide_button)

        # While the sidebar is hidden its Hide button goes with it, so a slim rail keeps a way back in view.
        self.rail = QWidget()
        self.rail.setFixedWidth(RAIL_WIDTH_PX)
        rail_layout = QVBoxLayout(self.rail)
        rail_layout.setContentsMargins(6, 14, 6, 14)
        self.show_button = QPushButton("☰")
        self.show_button.setProperty("nav", "true")
        self.show_button.setObjectName("showSidebar")
        self.show_button.setToolTip("Show the sidebar (Ctrl+B or Esc).")
        self.show_button.clicked.connect(self._show_sidebar)
        rail_layout.addWidget(self.show_button)
        rail_layout.addStretch(1)
        self.rail.hide()

        root = QWidget()
        root.setObjectName("simpleRoot")
        row = QHBoxLayout(root)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        row.addWidget(self.sidebar)
        row.addWidget(self.rail)
        row.addWidget(self.stack, 1)
        self.setCentralWidget(root)

        self.log_pane = popup_log_pane(self, session.log_bridge, self.theme)
        self.theme_menu = ThemeMenu(self, self.theme)
        self.sidebar_action = QAction("&Sidebar", self)
        self.sidebar_action.setCheckable(True)
        self.sidebar_action.setChecked(True)
        self.sidebar_action.setShortcut(QKeySequence("Ctrl+B"))
        self.sidebar_action.toggled.connect(self.set_sidebar_visible)
        self.theme_menu.add_action(self.sidebar_action)
        self.theme_menu.add_action(self.log_pane.view_action)
        QShortcut(QKeySequence("Esc"), self, activated=self._show_sidebar)

        self.dashboard_page.event_log_requested.connect(self._show_event_log)
        self.event_log_page.log_requested.connect(self.log_pane.view_action.trigger)
        self.settings_page.apply_requested.connect(self._apply_setup)
        self.theme.changed.connect(self._apply_palette)
        self._apply_palette(self.theme.palette)
        self.show_page(DASHBOARD)

    @property
    def current_page_name(self) -> str:
        return next(name for name, page in self.pages.items() if page is self.stack.currentWidget())

    def show_page(self, name: str) -> None:
        """Bring a page to the front and mark its sidebar button."""
        self.stack.setCurrentWidget(self.pages[name])
        self.nav_buttons[name].setChecked(True)

    def closeEvent(self, event) -> None:
        log.debug("Window closed: Simple")
        self.analysis_page.shutdown()
        self.settings_page.shutdown()
        super().closeEvent(event)

    def _on_nav_clicked(self, *_args) -> None:
        self.show_page(self.sender().text())

    def _show_event_log(self) -> None:
        self.show_page(EVENT_LOG)

    @property
    def sidebar_visible(self) -> bool:
        return not self.sidebar.isHidden()

    def set_sidebar_visible(self, visible: bool) -> None:
        """Show or hide the sidebar. Hidden, a slim rail with a show button stays; the Hide button and
        View > Sidebar follow."""
        self.sidebar.setVisible(visible)
        self.rail.setVisible(not visible)
        for control, state in ((self.hide_button, not visible), (self.sidebar_action, visible)):
            control.blockSignals(True)
            control.setChecked(state)
            control.blockSignals(False)

    def _on_hide_toggled(self, hidden: bool) -> None:
        self.set_sidebar_visible(not hidden)

    def _show_sidebar(self, *_args) -> None:
        self.set_sidebar_visible(True)

    def _apply_setup(self, config: RunConfig) -> None:
        self.session.apply_config(config)
        self.show_page(DASHBOARD)

    def _apply_palette(self, palette: Palette) -> None:
        self.setStyleSheet(simple_stylesheet(palette))
