import pytest
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

from pvysics.gui.app import main
from pvysics.gui.session import Session

HMI_TITLE = "PV Digital Twin"
DASHBOARD_TITLE = "PV Digital Twin Dashboard"
SENSORS_TITLE = "PV Digital Twin Sensors"
SIMPLE_TITLE = "PV Digital Twin"


def test_main_window_opens_with_project_title_and_closes(qtbot):
    window = Session().open_hmi()
    qtbot.addWidget(window)

    window.show()
    qtbot.waitExposed(window)
    assert window.windowTitle() == "PV Digital Twin"

    window.close()
    assert not window.isVisible()


def windows_visible_when_main_runs(argv: list[str]) -> list[str]:
    """Runs the console entry point with argv and returns the titles of the windows it showed."""
    visible_titles = []

    def inspect_and_quit():
        visible_titles.extend(w.windowTitle() for w in QApplication.topLevelWidgets() if w.isVisible())
        QApplication.quit()

    QTimer.singleShot(0, inspect_and_quit)

    assert main(argv, splash=False) == 0
    return visible_titles


def test_console_entry_point_with_both_shows_both_windows_and_exits_cleanly():
    titles = windows_visible_when_main_runs(["--both"])

    assert HMI_TITLE in titles
    assert DASHBOARD_TITLE in titles


def test_no_switch_opens_the_hmi_the_dashboard_and_the_sensors_window():
    titles = windows_visible_when_main_runs([])

    assert sorted(titles) == sorted([HMI_TITLE, DASHBOARD_TITLE, SENSORS_TITLE])


def test_sensors_switch_opens_only_the_sensors_window():
    assert windows_visible_when_main_runs(["--sensors"]) == [SENSORS_TITLE]


def test_hmi_switch_opens_only_the_hmi():
    assert windows_visible_when_main_runs(["--hmi"]) == [HMI_TITLE]


def test_dashboard_switch_opens_only_the_dashboard():
    assert windows_visible_when_main_runs(["--dashboard"]) == [DASHBOARD_TITLE]


def test_without_the_advanced_flag_one_simple_window_opens(monkeypatch):
    monkeypatch.delenv("PVYSICS_ADVANCED_VERSION")

    assert windows_visible_when_main_runs([]) == [SIMPLE_TITLE]


def test_unknown_switch_exits_with_usage_before_any_window_opens(capsys):
    with pytest.raises(SystemExit) as exit_info:
        main(["--nope"])

    assert exit_info.value.code != 0
    assert "usage: pvysics" in capsys.readouterr().err


def test_wayland_platform_noise_is_dropped_and_real_qt_messages_are_kept():
    from pvysics.gui.app import is_harmless

    assert is_harmless("This plugin supports grabbing the mouse only for popup windows")
    assert is_harmless("QGraphicsView::dragLeaveEvent: drag leave received before drag enter")
    assert not is_harmless("QObject::connect: invalid nullptr parameter")
