import sys

from PyQt6.QtCore import QtMsgType, qInstallMessageHandler
from PyQt6.QtQuick import QQuickWindow, QSGRendererInterface
from PyQt6.QtWidgets import QApplication

from pvysics.gui.cli import ALL, BOTH, DASHBOARD, HMI, SENSORS, parse_opening
from pvysics.gui.fonts import install as install_fonts
from pvysics.gui.session import Session


# Qt prints these on Wayland whenever a chart is dragged or a dock is moved. They report a platform limit, not a
# fault in the app, and nothing breaks, so they are dropped. Every other Qt message still reaches stderr.
HARMLESS_QT_MESSAGES = (
    "This plugin supports grabbing the mouse only for popup windows",
    "QGraphicsView::dragLeaveEvent: drag leave received before drag enter",
    "This plugin does not support propagateSizeHints()",
    "This plugin does not support raise()",
)


def is_harmless(message: str) -> bool:
    """True for the Qt platform messages that are noise, not problems."""
    return any(known in message for known in HARMLESS_QT_MESSAGES)


def _qt_message(kind: QtMsgType, _context, message: str) -> None:
    if not is_harmless(message):
        print(message, file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    """Run the app. Switches on the command line choose the windows to open; none opens all three windows."""
    opening = parse_opening(sys.argv[1:] if argv is None else argv)  # a bad switch exits before Qt starts
    # The QML figures are flat type and a few rectangles: software rendering needs no GPU and looks the same everywhere.
    QQuickWindow.setGraphicsApi(QSGRendererInterface.GraphicsApi.Software)
    qInstallMessageHandler(_qt_message)
    app = QApplication.instance() or QApplication(sys.argv)
    install_fonts(app)
    app.setOrganizationName("pvysics")  # names the QSettings store, which is platform-neutral
    app.setApplicationName("pvysics")
    session = Session()  # one run for the whole app; it lives as long as the event loop
    show_windows(session, opening)
    code = app.exec()
    session.close()  # removes the log handler; the run ends with the event loop
    return code


def show_windows(session: Session, opening: str) -> None:
    if opening in (HMI, BOTH, ALL):
        session.open_hmi()
    if opening in (DASHBOARD, BOTH, ALL):
        session.open_dashboard()
    if opening in (SENSORS, ALL):
        session.open_sensors()
