"""The launcher: a small window that opens the HMI, the Dashboard or both.

It holds no run. It asks the session to show a window, which raises the window if it is open.
"""

import logging
from importlib.metadata import PackageNotFoundError, version
from typing import TYPE_CHECKING

from PyQt6.QtWidgets import QMainWindow, QPushButton, QVBoxLayout, QWidget

from pvysics.gui.theme import ThemeMenu
from pvysics.gui.ui_helpers import role_label, set_property

if TYPE_CHECKING:
    from pvysics.gui.session import Session

APP_NAME = "PV Digital Twin"
MIN_WIDTH_PX = 380
log = logging.getLogger(__name__)


def app_version() -> str:
    try:
        return version("pvysics")
    except PackageNotFoundError:  # run from a source tree that is not installed
        return "unknown"


TAGLINE = "Physics-informed digital twin for PV state estimation"
CHOICES = (
    ("open_hmi_button", "Open HMI", "Run the plant and the twin, inject faults, set up the run.", False),
    ("open_dashboard_button", "Open Dashboard", "Read-only charts, events and validation for the run.", False),
    ("open_both_button", "Open both", "The HMI to drive, the Dashboard to watch. The usual choice for a demo.", True),
)


class Launcher(QMainWindow):
    """Open HMI, Open Dashboard and Open both. Closing it leaves any window it opened running."""

    def __init__(self, session: "Session") -> None:
        super().__init__()
        self.setWindowTitle("PV Digital Twin Launcher")
        actions = {
            "open_hmi_button": lambda *_: session.open_hmi(),
            "open_dashboard_button": lambda *_: session.open_dashboard(),
            "open_both_button": lambda *_: _open_both(session),
        }
        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(28, 24, 28, 20)
        layout.setSpacing(6)
        layout.addWidget(role_label(APP_NAME, "title"))
        tagline = role_label(TAGLINE, "muted")
        tagline.setWordWrap(True)
        layout.addWidget(tagline)
        layout.addSpacing(14)
        for attribute, label, description, primary in CHOICES:
            button = QPushButton(label)
            if primary:
                set_property(button, "variant", "primary")
            button.clicked.connect(actions[attribute])
            setattr(self, attribute, button)
            layout.addWidget(button)
            caption = role_label(description, "caption")
            caption.setWordWrap(True)
            layout.addWidget(caption)
            layout.addSpacing(8)
        layout.addStretch(1)
        layout.addWidget(role_label(f"Version {app_version()}", "caption"))
        self.setCentralWidget(central)
        self.setMinimumWidth(MIN_WIDTH_PX)
        ThemeMenu(self, session.theme)

    def closeEvent(self, event) -> None:
        log.debug("Window closed: Launcher")
        super().closeEvent(event)


def _open_both(session: "Session") -> None:
    session.open_hmi()
    session.open_dashboard()
