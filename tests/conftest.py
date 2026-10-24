import os
import sys

import pytest

# Run Qt without a display server so the tests pass headless on any platform.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QEvent, QSettings
from PyQt6.QtQuick import QQuickWindow, QSGRendererInterface
from PyQt6.QtWidgets import QApplication

from pvysics.gui.session import Session

QQuickWindow.setGraphicsApi(QSGRendererInterface.GraphicsApi.Software)  # as the app does: no GPU needed


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
    result = yield
    # The windows are gone now (pytest-qt deleted them). Delete the sessions too: a session is parented to the
    # application, so it would otherwise live on, and every surviving session re-applies the stylesheet when the
    # system colour scheme changes, which restyles every widget left over. That cost grows with each test.
    if app is not None:
        for session in app.findChildren(Session):
            session.deleteLater()
        app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    return result


def pytest_sessionfinish(session, exitstatus):
    """Keep one harmless pyqtgraph shutdown message out of the output.

    As the last window is torn down, pyqtgraph resizes a LabelItem that is not fully built and PyQt prints a
    KeyError for its missing "justify" option. It is raised inside pyqtgraph's own virtual method, after every
    test has finished, so the hook drops that one error and passes every other through.
    """
    previous = sys.excepthook

    def hook(kind, value, trace):
        if kind is KeyError and value.args == ("justify",):
            return
        previous(kind, value, trace)

    sys.excepthook = hook
