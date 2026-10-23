import sys

from PyQt6.QtWidgets import QApplication

from pvysics.gui.cli import BOTH, DASHBOARD, HMI, LAUNCHER, parse_opening
from pvysics.gui.session import Session


def main(argv: list[str] | None = None) -> int:
    """Run the app. Switches on the command line choose the windows to open; none opens the launcher."""
    opening = parse_opening(sys.argv[1:] if argv is None else argv)  # a bad switch exits before Qt starts
    app = QApplication.instance() or QApplication(sys.argv)
    app.setOrganizationName("pvysics")  # names the QSettings store, which is platform-neutral
    app.setApplicationName("pvysics")
    session = Session()  # one run for the whole app; it lives as long as the event loop
    show_windows(session, opening)
    return app.exec()


def show_windows(session: Session, opening: str) -> None:
    if opening == LAUNCHER:
        session.open_launcher()
    if opening in (HMI, BOTH):
        session.open_hmi()
    if opening in (DASHBOARD, BOTH):
        session.open_dashboard()
