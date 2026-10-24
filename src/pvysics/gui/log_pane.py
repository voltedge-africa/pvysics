"""The log pane: a collapsible bottom dock that shows the session's LogModel.

Each window docks one pane at its bottom. Both panes show the same model, so they list the same
lines and share the level filter. The pane has a level filter, Clear and Copy (Copy puts the visible
text on the clipboard), and it colours warning and error lines from the theme palette. New lines
arrive through the bridge and are drawn on a UI tick. The view follows the newest line unless the
user has scrolled up. Collapsing keeps the header row and hides the list; Hide removes the pane, and the window's
View > Show log (Ctrl+L) brings it back.
"""

import logging

from PyQt6.QtCore import QSignalBlocker, QSize, Qt, QTimer
from PyQt6.QtGui import QColor, QFontDatabase, QFontMetrics, QGuiApplication, QTextCharFormat, QTextCursor
from PyQt6.QtWidgets import (
    QComboBox,
    QDockWidget,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QTextEdit,
    QToolButton,
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
DEFAULT_LINES = 5  # the list is this tall when the pane first opens


def line_colour(entry: LogEntry, palette: Palette) -> str | None:
    """The palette colour of a log line, or None for a plain line. Only warnings and errors are coloured."""
    if entry.level >= logging.ERROR:
        return palette.error
    if entry.level >= logging.WARNING:
        return palette.warning
    return None


class LogPane(QDockWidget):
    """The log dock. Build it with bottom_log_pane, which docks it in a window."""

    def __init__(self, bridge: LogBridge, theme: ThemeManager, parent: QWidget | None = None) -> None:
        super().__init__("Log", parent)
        self.setObjectName("log_pane")
        # Closable, or Qt disables the View > Show log action. The empty title bar below shows no close button.
        self.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetClosable)
        self.setTitleBarWidget(QWidget())  # the header row below is the title
        self._bridge = bridge
        self._palette = theme.palette
        self._collapsed = False
        self._dirty = True

        self.collapse_button = QToolButton()
        self.collapse_button.setText("Log")
        self.collapse_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.collapse_button.setCheckable(True)
        self.collapse_button.setChecked(True)
        self.collapse_button.setArrowType(Qt.ArrowType.DownArrow)
        self.collapse_button.toggled.connect(self._on_collapse_toggled)

        self.level_box = QComboBox()
        for label, level in LEVEL_CHOICES:
            self.level_box.addItem(label, level)
        self.level_box.setCurrentIndex(self.level_box.findData(bridge.model.threshold))
        self.level_box.currentIndexChanged.connect(self._on_level_chosen)
        self.clear_button = QPushButton("Clear")
        self.clear_button.clicked.connect(self._on_clear_clicked)
        self.copy_button = QPushButton("Copy")
        self.copy_button.clicked.connect(self._on_copy_clicked)
        self.hide_button = QPushButton("Hide")
        self.hide_button.setToolTip("Hide the log. View > Show log (Ctrl+L) brings it back.")
        self.hide_button.clicked.connect(self._on_hide_clicked)
        # The window's View menu shows this action checked while the pane is visible, and toggles it.
        self.view_action = self.toggleViewAction()
        self.view_action.setText("Show &log")
        self.view_action.setShortcut("Ctrl+L")

        self.text_view = QPlainTextEdit()
        self.text_view.setReadOnly(True)
        self.text_view.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        # Two lines is the least that is useful. The dock still opens at DEFAULT_LINES, so a short window can shrink.
        self.text_view.setMinimumHeight(QFontMetrics(self.text_view.font()).lineSpacing() * 2 + 12)

        header = QHBoxLayout()
        header.addWidget(self.collapse_button)
        header.addStretch(1)
        header.addWidget(QLabel("Level"))
        header.addWidget(self.level_box)
        header.addWidget(self.clear_button)
        header.addWidget(self.copy_button)
        header.addWidget(self.hide_button)
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

    @property
    def is_collapsed(self) -> bool:
        return self._collapsed

    def set_collapsed(self, collapsed: bool) -> None:
        """Hide the list and keep the header, or show the list again."""
        self._collapsed = collapsed
        self.text_view.setVisible(not collapsed)
        with QSignalBlocker(self.collapse_button):  # the button's own toggle already did this
            self.collapse_button.setChecked(not collapsed)
        self.collapse_button.setArrowType(Qt.ArrowType.RightArrow if collapsed else Qt.ArrowType.DownArrow)
        self.fit_height()

    def fit_height(self) -> None:
        """Give the dock its height for the current state: the header when collapsed, else a few lines."""
        window = self.parentWidget()
        if isinstance(window, QMainWindow):
            for layout in (self._content.layout(), self.widget().layout()):
                layout.invalidate()  # a list shown or hidden changes the layout's size hint
                layout.activate()
            window.resizeDocks([self], [self.sizeHint().height()], Qt.Orientation.Vertical)

    def sizeHint(self) -> QSize:
        """The header and, when expanded, DEFAULT_LINES lines of the list, not the list's full size hint."""
        hint = super().sizeHint()
        if self._collapsed:
            return hint  # the hidden list takes no room
        line = QFontMetrics(self.text_view.font()).lineSpacing()
        list_height = self.text_view.sizeHint().height()
        return QSize(hint.width(), hint.height() - list_height + DEFAULT_LINES * line)

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

    def _on_hide_clicked(self, *_args) -> None:
        self.hide()

    def _on_copy_clicked(self, *_args) -> None:
        QGuiApplication.clipboard().setText(self.visible_text())

    def _on_collapse_toggled(self, checked: bool) -> None:
        self.set_collapsed(not checked)


def bottom_log_pane(window: QMainWindow, bridge: LogBridge, theme: ThemeManager) -> LogPane:
    """Dock a log pane along the bottom of window and return it."""
    pane = LogPane(bridge, theme, window)
    window.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, pane)
    pane.fit_height()  # start small
    return pane
