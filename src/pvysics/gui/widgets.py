"""Small widgets shared by the Dashboard and its tabs. No run logic here."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QVBoxLayout, QWidget

from pvysics.gui.process_view import PLACEHOLDER
from pvysics.gui.ui_helpers import role_label


class KpiTile(QFrame):
    """A headline number with its caption, as a card. A tile can be tinted, as the State tile is."""

    def __init__(self, caption: str, parent: QWidget | None = None, tooltip: str = "") -> None:
        super().__init__(parent)
        self.setProperty("card", "true")
        self._colour: str | None = None
        self._value = role_label(PLACEHOLDER, "value", Qt.AlignmentFlag.AlignCenter)
        layout = QVBoxLayout(self)
        layout.addWidget(role_label(caption, "caption", Qt.AlignmentFlag.AlignCenter))
        layout.addWidget(self._value)
        if tooltip:  # what the figure means, on hover, so the tile stays short
            self.setToolTip(tooltip)

    def text(self) -> str:
        return self._value.text()

    def colour(self) -> str | None:
        return self._colour

    def set_value(self, text: str, colour: str | None = None, text_colour: str = "#000000") -> None:
        self._colour = colour
        self._value.setText(text)
        style = (
            f"background-color: {colour}; color: {text_colour}; border-radius: 6px; padding: 1px 12px;"
            if colour
            else ""
        )
        self._value.setStyleSheet(style)
