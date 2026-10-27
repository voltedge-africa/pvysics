"""The simple window's look: a sidebar, boxed cards and large figures, in the app's own palette. No Qt imports.

It is set on the simple window and adds to the app stylesheet (gui/style.py), which already restyles buttons,
fields, tables and tabs from the same Palette. Widgets opt in with Qt properties, as there:

    card    "true" a boxed panel with a rounded border
    role    "pageTitle", "pageSub", "cardTitle", "cardSub", "kpi", "kpiUnit", "deviation", "chip", "brand", "brandSub"
    nav     "true" a sidebar button
"""

from pvysics.gui.palette import Palette

CARD_RADIUS_PX = 10


def simple_stylesheet(palette: Palette) -> str:
    """The simple window's stylesheet for a palette."""
    p = palette
    return f"""
#simpleRoot {{ background-color: {p.window}; }}

#simpleSidebar {{ background-color: {p.base}; border-right: 1px solid {p.card_border}; }}
QLabel[role="brand"] {{ font-size: 15pt; font-weight: 800; }}
QLabel[role="brandSub"] {{ color: {p.muted_text}; font-size: 9pt; }}
QPushButton[nav="true"] {{
    text-align: left;
    padding: 11px 16px;
    border: none;
    border-radius: 8px;
    background-color: transparent;
    color: {p.text};
    font-size: 11pt;
}}
QPushButton[nav="true"]:hover {{ background-color: {p.card}; }}
QPushButton[nav="true"]:checked {{ background-color: {p.card}; border: 1px solid {p.card_border}; font-weight: 600; }}

#showSidebar {{ font-size: 17pt; text-align: center; padding: 4px 0; }}

QFrame[card="true"] {{
    background-color: {p.card};
    border: 1px solid {p.card_border};
    border-radius: {CARD_RADIUS_PX}px;
}}
QFrame[card="true"] QLabel {{ background: transparent; border: none; }}

QLabel[role="pageTitle"] {{ font-size: 22pt; font-weight: 800; }}
QLabel[role="pageSub"] {{ color: {p.muted_text}; font-size: 10.5pt; }}
QLabel[role="cardTitle"] {{ font-size: 10.5pt; font-weight: 800; }}
QLabel[role="cardSub"] {{ color: {p.muted_text}; font-size: 9pt; }}
QLabel[role="deviation"] {{ font-size: 30pt; font-weight: 800; }}
QLabel[role="kpi"] {{ font-size: 20pt; font-weight: 700; }}
QLabel[role="kpiUnit"] {{ color: {p.muted_text}; font-size: 10pt; }}
QLabel[role="chip"] {{ font-size: 10pt; font-weight: 700; }}

QPushButton[variant="primary"] {{ padding: 8px 18px; }}
QPushButton[variant="primary"]:hover {{ border-color: {p.link}; }}
QPushButton[compact="true"] {{ padding: 2px 10px; min-height: 0; }}
"""
