"""The launcher: a small window that opens the HMI, the Dashboard or both.

It holds no run. It asks the session to show a window, which raises the window if it is open.
"""

from importlib.metadata import PackageNotFoundError, version
from typing import TYPE_CHECKING

from PyQt6.QtWidgets import QLabel, QMainWindow, QPushButton, QVBoxLayout, QWidget

from pvysics.gui.theme import ThemeMenu

if TYPE_CHECKING:
    from pvysics.gui.session import Session

APP_NAME = "PV Digital Twin"


def app_version() -> str:
    try:
        return version("pvysics")
    except PackageNotFoundError:  # run from a source tree that is not installed
        return "unknown"


class Launcher(QMainWindow):
    """Open HMI, Open Dashboard and Open both. Closing it leaves any window it opened running."""

    def __init__(self, session: "Session") -> None:
        super().__init__()
        self.setWindowTitle("PV Digital Twin Launcher")
        self.open_hmi_button = QPushButton("Open HMI")
        self.open_dashboard_button = QPushButton("Open Dashboard")
        self.open_both_button = QPushButton("Open both")
        self.open_hmi_button.clicked.connect(lambda *_: session.open_hmi())
        self.open_dashboard_button.clicked.connect(lambda *_: session.open_dashboard())
        self.open_both_button.clicked.connect(lambda *_: _open_both(session))

        title = QLabel(APP_NAME)
        title_font = title.font()
        title_font.setBold(True)  # the platform's own font, made bold
        title.setFont(title_font)
        central = QWidget()
        layout = QVBoxLayout(central)
        layout.addWidget(title)
        layout.addWidget(QLabel(f"Version {app_version()}"))
        for button in (self.open_hmi_button, self.open_dashboard_button, self.open_both_button):
            layout.addWidget(button)
        self.setCentralWidget(central)
        ThemeMenu(self, session.theme)


def _open_both(session: "Session") -> None:
    session.open_hmi()
    session.open_dashboard()
