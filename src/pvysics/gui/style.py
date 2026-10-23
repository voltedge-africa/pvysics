"""The look of the app as one stylesheet built from a Palette. No Qt imports: the rules are tested headless.

Fusion plus the QPalette (gui/theme.py) gives every platform the same base. This sheet adds the parts
a palette cannot say: group boxes as cards, buttons with a clear primary action, tabs with an accent
underline and a small type scale. Widgets opt in with Qt properties, so no widget carries its own colours:

    role   "caption" small muted text, "value" a figure, "hero" a headline figure, "title" a section heading,
           "muted" secondary text
    variant "primary" the one main action on a screen, "danger" a destructive action, "active" a toggled-on chip
"""

from pvysics.gui.palette import Palette

RADIUS_PX = 8
FIELD_PADDING_PX = 4


def stylesheet(palette: Palette) -> str:
    """The application stylesheet for a palette."""
    p = palette
    return f"""
QToolTip {{
    background-color: {p.base}; color: {p.text}; border: 1px solid {p.card_border}; padding: 4px;
}}

QGroupBox {{
    background-color: {p.card};
    border: 1px solid {p.card_border};
    border-radius: {RADIUS_PX}px;
    margin-top: 1.1em;
    padding: 0.9em 0.6em 0.6em 0.6em;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    padding: 0 6px;
    color: {p.muted_text};
    font-weight: 600;
}}

QFrame[card="true"] {{
    background-color: {p.card};
    border: 1px solid {p.card_border};
    border-radius: {RADIUS_PX}px;
}}
QFrame[card="true"] QLabel {{
    background: transparent;
    border: none;
}}

QLabel[role="caption"] {{ color: {p.muted_text}; font-size: 9pt; }}
QLabel[role="muted"] {{ color: {p.muted_text}; }}
QLabel[role="strong"] {{ font-weight: 600; }}
QLabel[role="value"] {{ font-size: 15pt; font-weight: 600; }}
QLabel[role="dirty"] {{ color: {p.warning}; font-weight: 600; }}
QLabel[role="metric"] {{ font-size: 22pt; font-weight: 700; }}
QLabel[role="unit"] {{ color: {p.muted_text}; font-size: 10pt; padding-bottom: 4px; }}
QLabel[role="section"] {{ color: {p.muted_text}; font-size: 8pt; font-weight: 700; }}
QLabel[role="hero"] {{ font-size: 22pt; font-weight: 700; }}
QLabel[role="title"] {{ font-size: 15pt; font-weight: 700; }}

QPushButton {{
    background-color: {p.card};
    color: {p.text};
    border: 1px solid {p.card_border};
    border-radius: 6px;
    padding: 5px 14px;
    min-height: 1.3em;
}}
QPushButton:hover {{ border-color: {p.highlight}; }}
QPushButton:pressed {{ background-color: {p.window}; }}
QPushButton:focus {{ border-color: {p.highlight}; }}
QPushButton:disabled {{ color: {p.muted_text}; background-color: {p.window}; border-color: {p.card_border}; }}
QPushButton[compact="true"] {{ padding: 2px 10px; min-height: 0; }}
QPushButton[variant="primary"] {{
    background-color: {p.highlight};
    color: {p.highlight_text};
    border-color: {p.highlight};
    font-weight: 600;
}}
QPushButton[variant="primary"]:hover {{ border-color: {p.text}; }}
QPushButton[variant="primary"]:disabled {{ background-color: {p.window}; color: {p.muted_text}; border-color: {p.card_border}; }}
QPushButton[variant="active"] {{
    background-color: {p.text};
    color: {p.window};
    border-color: {p.text};
    font-weight: 600;
}}

QMainWindow::separator {{ background: {p.card_border}; height: 5px; border-radius: 2px; }}
QMainWindow::separator:hover {{ background: {p.highlight}; }}

QTabWidget::pane {{ border: none; }}
QTabBar::tab {{
    background: transparent;
    color: {p.muted_text};
    padding: 6px 16px;
    margin: 4px 2px 6px 2px;
    border: 1px solid transparent;
    border-radius: 6px;
    font-weight: 600;
}}
QTabBar::tab:hover {{ color: {p.text}; }}
QTabBar::tab:selected {{
    color: {p.text};
    background-color: {p.card};
    border: 1px solid {p.card_border};
}}

QScrollArea {{ border: none; background: transparent; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}

QScrollBar:vertical {{ background: transparent; width: 12px; margin: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 12px; margin: 0; }}
QScrollBar::handle:vertical {{ background: {p.card_border}; border-radius: 5px; min-height: 32px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: {p.card_border}; border-radius: 5px; min-width: 32px; margin: 2px; }}
QScrollBar::handle:hover {{ background: {p.muted_text}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

QListWidget, QPlainTextEdit {{
    background-color: {p.base};
    border: 1px solid {p.card_border};
    border-radius: 6px;
}}

QProgressBar {{
    border: 1px solid {p.card_border};
    border-radius: 4px;
    background: {p.window};
    text-align: center;
}}
QProgressBar::chunk {{ background-color: {p.highlight}; border-radius: 3px; }}
"""
