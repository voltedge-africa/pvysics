"""Small widgets shared by the Dashboard and its tabs. No run logic here."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from pvysics.gui.process_view import PLACEHOLDER


class KpiTile(QFrame):
    """A headline number with its caption. A tile can be tinted, as the State tile is."""

    def __init__(self, caption: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self._colour: str | None = None
        self._value = QLabel(PLACEHOLDER)
        self._value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = self._value.font()
        font.setBold(True)
        self._value.setFont(font)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(caption), alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._value)

    def text(self) -> str:
        return self._value.text()

    def colour(self) -> str | None:
        return self._colour

    def set_value(self, text: str, colour: str | None = None, text_colour: str = "#000000") -> None:
        self._colour = colour
        self._value.setText(text)
        style = f"background-color: {colour}; color: {text_colour};" if colour else ""
        self._value.setStyleSheet(style)
