import sys

from PyQt6.QtQuick import QQuickWindow, QSGRendererInterface
from PyQt6.QtWidgets import QApplication

from pvysics.gui.cli import BOTH, DASHBOARD, HMI, parse_opening
from pvysics.gui.session import Session


def main(argv: list[str] | None = None) -> int:
    """Run the app. Switches on the command line choose the windows to open; none opens both windows."""
    opening = parse_opening(sys.argv[1:] if argv is None else argv)  # a bad switch exits before Qt starts
    # The QML figures are flat type and a few rectangles: software rendering needs no GPU and looks the same everywhere.
    QQuickWindow.setGraphicsApi(QSGRendererInterface.GraphicsApi.Software)
    app = QApplication.instance() or QApplication(sys.argv)
    app.setOrganizationName("pvysics")  # names the QSettings store, which is platform-neutral
    app.setApplicationName("pvysics")
    session = Session()  # one run for the whole app; it lives as long as the event loop
    show_windows(session, opening)
    code = app.exec()
    session.close()  # removes the log handler; the run ends with the event loop
    return code


def show_windows(session: Session, opening: str) -> None:
    if opening in (HMI, BOTH):
        session.open_hmi()
    if opening in (DASHBOARD, BOTH):
        session.open_dashboard()
