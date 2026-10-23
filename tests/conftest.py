import os

# Run Qt without a display server so the tests pass headless on any platform.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
