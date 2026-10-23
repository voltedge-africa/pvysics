from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication, QLabel

from pvysics.gui.dashboard import Dashboard
from pvysics.gui.launcher import app_version
from pvysics.gui.main_window import MainWindow
from pvysics.gui.session import Session
from pvysics.gui.theme import ThemeMenu

WATCHDOG_MS = 4000  # a quit rule that fails would otherwise hang the suite


def visible_of(kind) -> list:
    return [w for w in QApplication.topLevelWidgets() if isinstance(w, kind) and w.isVisible()]


def open_launcher(qtbot):
    session = Session()
    launcher = session.open_launcher()
    qtbot.addWidget(launcher)
    return session, launcher


def test_open_hmi_button_opens_only_the_hmi(qtbot):
    session, launcher = open_launcher(qtbot)

    launcher.open_hmi_button.click()

    qtbot.addWidget(session.hmi)
    assert session.hmi_open
    assert visible_of(Dashboard) == []


def test_open_dashboard_button_opens_only_the_dashboard(qtbot):
    session, launcher = open_launcher(qtbot)

    launcher.open_dashboard_button.click()

    qtbot.addWidget(session.dashboard)
    assert session.dashboard.isVisible()
    assert visible_of(MainWindow) == []


def test_open_both_button_opens_both_windows(qtbot):
    session, launcher = open_launcher(qtbot)

    launcher.open_both_button.click()

    qtbot.addWidget(session.hmi)
    qtbot.addWidget(session.dashboard)
    assert len(visible_of(MainWindow)) == 1
    assert len(visible_of(Dashboard)) == 1


def test_clicking_an_open_window_again_raises_it_without_a_duplicate(qtbot, monkeypatch):
    session, launcher = open_launcher(qtbot)
    launcher.open_hmi_button.click()
    qtbot.addWidget(session.hmi)
    first = session.hmi
    raised = []
    monkeypatch.setattr(first, "raise_", lambda: raised.append(True))

    launcher.open_hmi_button.click()
    launcher.open_both_button.click()

    assert session.hmi is first
    assert len(visible_of(MainWindow)) == 1
    assert raised == [True, True]


def test_a_closed_window_is_reopened_from_the_launcher(qtbot):
    session, launcher = open_launcher(qtbot)
    launcher.open_hmi_button.click()
    qtbot.addWidget(session.hmi)
    session.hmi.close()

    launcher.open_hmi_button.click()

    assert session.hmi.isVisible()


def test_launcher_shows_the_app_name_version_and_a_view_menu(qtbot):
    _session, launcher = open_launcher(qtbot)

    texts = [label.text() for label in launcher.findChildren(QLabel)]

    assert any("PV Digital Twin" in text for text in texts)
    assert any(app_version() in text for text in texts)
    assert len(launcher.findChildren(ThemeMenu)) == 1


def test_closing_the_last_visible_window_quits_the_application(qtbot):
    _session, launcher = open_launcher(qtbot)
    app = QApplication.instance()
    timed_out = []

    def give_up():
        timed_out.append(True)
        app.quit()

    QTimer.singleShot(0, launcher.close)
    QTimer.singleShot(WATCHDOG_MS, give_up)
    app.exec()

    assert timed_out == []


def test_closing_the_launcher_while_the_hmi_is_open_does_not_quit(qtbot):
    session, launcher = open_launcher(qtbot)
    launcher.open_hmi_button.click()
    qtbot.addWidget(session.hmi)
    app = QApplication.instance()
    seen = {}

    def check_then_quit():
        seen["hmi_visible"] = session.hmi.isVisible()
        seen["launcher_visible"] = launcher.isVisible()
        app.quit()

    QTimer.singleShot(0, launcher.close)
    QTimer.singleShot(200, check_then_quit)
    app.exec()

    assert seen == {"hmi_visible": True, "launcher_visible": False}


def test_a_hidden_window_does_not_keep_the_application_running(qtbot):
    session = Session()
    session.open_hmi().close()  # hidden but alive: must not count as open
    dashboard = session.open_dashboard()
    app = QApplication.instance()
    timed_out = []

    def give_up():
        timed_out.append(True)
        app.quit()

    QTimer.singleShot(0, dashboard.close)
    QTimer.singleShot(WATCHDOG_MS, give_up)
    app.exec()

    assert timed_out == []
