"""The log pane: a pop-up window, opened from View > Logs (Ctrl+L), that shows the session's LogModel.

Each window owns one pane. It floats above the window, hidden until asked for, so the log never takes room
from the work. Both panes show the same model, so they list the same lines and share the level filter. The pane
has a level filter, Clear and Copy (Copy puts the visible text on the clipboard), and it colours warning and
error lines from the theme palette. New lines arrive through the bridge and are drawn on a UI tick. The view
follows the newest line unless the user has scrolled up.
"""

import logging

from PyQt6.QtCore import QSize, Qt, QTimer
from PyQt6.QtGui import QColor, QFontDatabase, QGuiApplication, QTextCharFormat, QTextCursor
from PyQt6.QtWidgets import (
    QComboBox,
    QDockWidget,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from pvysics.gui.log_bridge import LogBridge
from pvysics.gui.palette import Palette
from pvysics.gui.theme import ThemeManager
from pvysics.gui.ui_helpers import pane
from pvysics.log_model import LogEntry, format_entry

LEVEL_CHOICES = (
    ("Debug", logging.DEBUG),
    ("Info", logging.INFO),
    ("Warning", logging.WARNING),
    ("Error", logging.ERROR),
)
UI_INTERVAL_MS = 100  # new lines are drawn at most this often
POPUP_SIZE = QSize(720, 320)  # the pop-up opens this big


def line_colour(entry: LogEntry, palette: Palette) -> str | None:
    """The palette colour of a log line, or None for a plain line. Only warnings and errors are coloured."""
    if entry.level >= logging.ERROR:
        return palette.error
    if entry.level >= logging.WARNING:
        return palette.warning
    return None


class LogPane(QDockWidget):
    """The log pop-up. Build it with popup_log_pane."""

    def __init__(self, bridge: LogBridge, theme: ThemeManager, parent: QWidget | None = None) -> None:
        super().__init__("Log", parent)
        self.setObjectName("log_pane")
        # Closable, or Qt disables the View > Logs action; the close button on the pop-up's title bar hides it again.
        self.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetClosable | QDockWidget.DockWidgetFeature.DockWidgetMovable)
        self._bridge = bridge
        self._palette = theme.palette
        self._dirty = True

        self.level_box = QComboBox()
        for label, level in LEVEL_CHOICES:
            self.level_box.addItem(label, level)
        self.level_box.setCurrentIndex(self.level_box.findData(bridge.model.threshold))
        self.level_box.currentIndexChanged.connect(self._on_level_chosen)
        self.clear_button = QPushButton("Clear")
        self.clear_button.clicked.connect(self._on_clear_clicked)
        self.copy_button = QPushButton("Copy")
        self.copy_button.clicked.connect(self._on_copy_clicked)
        # The window's View menu shows this action checked while the pop-up is open, and toggles it.
        self.view_action = self.toggleViewAction()
        self.view_action.setText("&Logs")
        self.view_action.setShortcut("Ctrl+L")

        self.text_view = QPlainTextEdit()
        self.text_view.setReadOnly(True)
        self.text_view.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))

        header = QHBoxLayout()
        header.addStretch(1)
        header.addWidget(QLabel("Level"))
        header.addWidget(self.level_box)
        header.addWidget(self.clear_button)
        header.addWidget(self.copy_button)
        layout = QVBoxLayout()
        layout.addLayout(header)
        layout.addWidget(self.text_view, 1)
        content = QWidget()
        content.setLayout(layout)
        self._content = content
        self.setWidget(pane(content))

        bridge.updated.connect(self._mark_dirty)
        theme.changed.connect(self._on_palette_changed)
        self._timer = QTimer(self)
        self._timer.setInterval(UI_INTERVAL_MS)
        self._timer.timeout.connect(self._on_tick)
        self._timer.start()

    def visible_text(self) -> str:
        """The text the list shows, which is also what Copy puts on the clipboard."""
        return self._bridge.model.as_text()

    def line_colours(self) -> tuple[str | None, ...]:
        """The colour of each visible line, in order. None means the default text colour."""
        return tuple(line_colour(entry, self._palette) for entry in self._bridge.model.visible())

    def refresh(self) -> None:
        """Redraw the list from the model. The view keeps its place unless it was at the newest line."""
        self._dirty = False
        entries = self._bridge.model.visible()
        bar = self.text_view.verticalScrollBar()
        at_newest = bar.value() >= bar.maximum()
        position = bar.value()
        self.text_view.setPlainText("\n".join(format_entry(entry) for entry in entries))
        self.text_view.setExtraSelections(self._colour_selections(entries))
        bar.setValue(bar.maximum() if at_newest else position)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.refresh()  # catch up with lines that arrived while the pane was hidden

    def _colour_selections(self, entries: tuple[LogEntry, ...]) -> list[QTextEdit.ExtraSelection]:
        document = self.text_view.document()
        selections = []
        for index, entry in enumerate(entries):
            colour = line_colour(entry, self._palette)
            if colour is None:
                continue
            cursor = QTextCursor(document.findBlockByNumber(index))  # one block per line
            cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
            cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.KeepAnchor)
            changed = QTextCharFormat()
            changed.setForeground(QColor(colour))
            selection = QTextEdit.ExtraSelection()
            selection.cursor = cursor
            selection.format = changed
            selections.append(selection)
        return selections

    def _mark_dirty(self) -> None:
        self._dirty = True

    def _on_tick(self) -> None:
        if self._dirty:
            self.refresh()

    def _on_palette_changed(self, palette: Palette) -> None:
        self._palette = palette
        self.refresh()

    def _on_level_chosen(self, index: int) -> None:
        self._bridge.set_threshold(self.level_box.itemData(index))
        self.refresh()

    def _on_clear_clicked(self, *_args) -> None:
        self._bridge.clear()
        self.refresh()

    def _on_copy_clicked(self, *_args) -> None:
        QGuiApplication.clipboard().setText(self.visible_text())


def popup_log_pane(window: QMainWindow, bridge: LogBridge, theme: ThemeManager) -> LogPane:
    """Make a log pop-up for window, hidden until View > Logs opens it."""
    pane = LogPane(bridge, theme, window)
    window.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, pane)
    pane.setFloating(True)
    pane.resize(POPUP_SIZE)
    pane.hide()
    return pane
