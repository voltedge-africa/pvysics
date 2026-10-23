import os

import pytest

# Run Qt without a display server so the tests pass headless on any platform.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings


@pytest.fixture(autouse=True)
def settings_in_temp_dir(tmp_path):
    """Every test reads and writes a temporary settings store, never the user's real settings."""
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(tmp_path))
    yield
