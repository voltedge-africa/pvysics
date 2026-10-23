import sys

from PyQt6.QtWidgets import QApplication

from pvysics.gui.data_bus import DataBus
from pvysics.gui.main_window import MainWindow


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    bus = DataBus()  # the single data bus for the app; every window subscribes to it
    window = MainWindow(bus=bus)
    window.show()
    window.open_dashboard()  # the Dashboard opens alongside the HMI
    return app.exec()
