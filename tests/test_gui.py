from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

from pvysics.gui.app import main
from pvysics.gui.main_window import MainWindow


def test_main_window_opens_with_project_title_and_closes(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)

    window.show()
    qtbot.waitExposed(window)
    assert window.windowTitle() == "PV Digital Twin"

    window.close()
    assert not window.isVisible()


def test_console_entry_point_shows_the_window_and_exits_cleanly(qtbot):
    visible_titles = []

    def inspect_and_quit():
        visible_titles.extend(w.windowTitle() for w in QApplication.topLevelWidgets() if w.isVisible())
        QApplication.quit()

    QTimer.singleShot(0, inspect_and_quit)

    assert main() == 0
    assert "PV Digital Twin" in visible_titles
    assert "PV Digital Twin Dashboard" in visible_titles  # the Dashboard opens alongside the HMI
