import sys
from importlib.resources import files

from PyQt6.QtCore import QSize, Qt, QtMsgType, qInstallMessageHandler
from PyQt6.QtGui import QIcon, QImage, QPainter, QPixmap
from PyQt6.QtQuick import QQuickWindow, QSGRendererInterface
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import QApplication, QSplashScreen

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


SPLASH_SIZE = QSize(800, 450)  # the splash image's own size, in logical pixels


def _asset(name: str) -> str:
    return str(files("pvysics.gui").joinpath("assets", name))


def splash_pixmap() -> QPixmap:
    """The splash image (assets/splash.svg) drawn sharp at the screen's pixel ratio."""
    ratio = QApplication.primaryScreen().devicePixelRatio() if QApplication.primaryScreen() else 1.0
    image = QImage(SPLASH_SIZE * ratio, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    QSvgRenderer(_asset("splash.svg")).render(painter)
    painter.end()
    pixmap = QPixmap.fromImage(image)
    pixmap.setDevicePixelRatio(ratio)
    return pixmap


def main(argv: list[str] | None = None, *, splash: bool = True) -> int:
    """Run the app. Switches on the command line choose the windows to open; none opens all three windows.

    The splash is painted by running the event loop briefly, so a caller that queues a timer for the loop passes
    splash=False."""
    opening = parse_opening(sys.argv[1:] if argv is None else argv)  # a bad switch exits before Qt starts
    # The QML figures are flat type and a few rectangles: software rendering needs no GPU and looks the same everywhere.
    QQuickWindow.setGraphicsApi(QSGRendererInterface.GraphicsApi.Software)
    qInstallMessageHandler(_qt_message)
    app = QApplication.instance() or QApplication(sys.argv)
    install_fonts(app)
    app.setOrganizationName("pvysics")  # names the QSettings store, which is platform-neutral
    app.setApplicationName("pvysics")
    app.setWindowIcon(QIcon(_asset("icon.svg")))
    screen = QSplashScreen(splash_pixmap()) if splash else None
    if screen:
        screen.show()
        screen.repaint()  # paint it now: the session and its windows take a while to build before the event loop runs
    session = Session()  # one run for the whole app; it lives as long as the event loop
    show_windows(session, opening)
    if screen:
        screen.close()
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
