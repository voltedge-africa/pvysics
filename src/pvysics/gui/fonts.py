"""The app's typefaces: Barlow, bundled so the app looks the same on every platform.

Barlow is drawn after road and rail signage: plain, a little condensed, easy to read at a glance. Its
Semi Condensed cut carries the large live figures. Digits are set tabular (tnum), so a figure that
changes every tick does not jitter sideways as 1 and 8 swap places.
"""

from pathlib import Path

from PyQt6.QtGui import QFont, QFontDatabase, QGuiApplication

FONT_DIR = Path(__file__).with_name("fonts")
TEXT_FAMILY = "Barlow"
FIGURE_FAMILY = "Barlow Semi Condensed"
TEXT_POINT_SIZE = 10.5

_loaded = False


def load_fonts() -> None:
    """Register the bundled fonts with Qt. Safe to call again."""
    global _loaded
    if _loaded:
        return
    for file in sorted(FONT_DIR.glob("*.ttf")):
        QFontDatabase.addApplicationFont(str(file))
    _loaded = True


def app_font() -> QFont:
    """The font for the whole app: Barlow with tabular digits."""
    load_fonts()
    font = QFont(TEXT_FAMILY)
    font.setPointSizeF(TEXT_POINT_SIZE)
    font.setFeature(QFont.Tag("tnum"), 1)
    return font


def install(app: QGuiApplication) -> None:
    app.setFont(app_font())
