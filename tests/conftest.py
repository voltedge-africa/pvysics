import os

import pytest

# Run Qt without a display server so the tests pass headless on any platform.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QApplication

from pvysics.gui.session import Session


@pytest.fixture(autouse=True)
def settings_in_temp_dir(tmp_path):
    """Every test reads and writes a temporary settings store, never the user's real settings."""
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(tmp_path))
    yield


@pytest.hookimpl(wrapper=True, tryfirst=True)
def pytest_runtest_teardown(item):
    """Before pytest-qt deletes the test's windows: pause every run, detach every log handler and close every window.

    A session can outlive its test, and a run still ticking would reach a window that qtbot has
    deleted. Windows that a test opened without qtbot (for example through main) are closed here too,
    so a later test that relies on the last visible window closing does not see them as open.
    """
    app = QApplication.instance()
    if app is not None:
        for session in app.findChildren(Session):
            session.playback.pause()
            session.close()  # detaches the session's log handler, so no test leaks one into the next
        for widget in app.topLevelWidgets():
            widget.close()
    return (yield)
