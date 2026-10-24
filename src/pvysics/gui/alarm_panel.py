"""Alarms: what the Dashboard lists when the twin and the plant disagree.

The AlarmMonitor belongs to the session, so alarms are recorded and logged whichever windows are open. The
Dashboard's AlarmPanel shows the monitor's list, newest first, with unacknowledged alarms in bold and tinted by
severity, and lets the user acknowledge them.
"""

import logging

import numpy as np
from PyQt6.QtCore import QEvent, QObject, Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QFont, QPalette
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton, QVBoxLayout, QWidget

from pvysics.alarms import Alarm, AlarmLog
from pvysics.gui.data_bus import DataBus
from pvysics.gui.palette import STATE_COLOURS
from pvysics.run import Sample, State

log = logging.getLogger(__name__)


def format_alarm(alarm: Alarm) -> str:
    stamp = np.datetime_as_string(alarm.timestamp, unit="s").split("T")[1]
    text = f"{stamp}  {alarm.severity.value.upper()}  {abs(alarm.deviation_pct):.1f} %  {alarm.cause}"
    return f"{text}  (seen)" if alarm.acknowledged else text


def log_alarm(alarm: Alarm) -> None:
    """A Warning alarm logs a WARNING line and an Abnormal alarm an ERROR line."""
    level = logging.ERROR if alarm.severity is State.ABNORMAL else logging.WARNING
    log.log(
        level,
        "Alarm %s: deviation %.1f %%, probable cause: %s",
        alarm.severity.value,
        abs(alarm.deviation_pct),
        alarm.cause,
    )


class AlarmMonitor(QObject):
    """Records an alarm when a Sample starts one, logs it, and says when the list changed."""

    changed = pyqtSignal()

    def __init__(self, bus: DataBus, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.log = AlarmLog()
        bus.sample.connect(self._on_sample)
        bus.run_reset.connect(self._on_reset)

    def acknowledge(self, index: int) -> None:
        self.log.acknowledge(index)
        alarm = self.log.alarms[index]
        log.info("Alarm acknowledged: %s, probable cause: %s", alarm.severity.value, alarm.cause)
        self.changed.emit()

    def _on_sample(self, sample: Sample) -> None:
        alarm = self.log.record(sample)
        if alarm is not None:
            log_alarm(alarm)
            self.changed.emit()

    def _on_reset(self) -> None:
        self.log.clear()
        self.changed.emit()


class AlarmPanel(QWidget):
    """The alarm list, newest first. Unacknowledged alarms are bold and tinted by severity."""

    def __init__(self, monitor: AlarmMonitor, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._monitor = monitor
        self.log = monitor.log
        self.summary_label = QLabel()
        self.list_widget = QListWidget()
        self.list_widget.setWordWrap(True)
        self.list_widget.setTextElideMode(Qt.TextElideMode.ElideNone)
        self.list_widget.setMinimumHeight(self.fontMetrics().height() * 3)  # three rows; it scrolls when more
        self.acknowledge_button = QPushButton("Acknowledge")
        self.acknowledge_button.setEnabled(False)

        header = QHBoxLayout()
        header.addWidget(self.summary_label)
        header.addStretch(1)
        header.addWidget(self.acknowledge_button)
        layout = QVBoxLayout(self)
        layout.addLayout(header)
        layout.addWidget(self.list_widget)

        self.acknowledge_button.clicked.connect(self._acknowledge_selected)
        self.list_widget.itemSelectionChanged.connect(self._refresh_buttons)
        monitor.changed.connect(self._refresh)
        self._refresh()

    def changeEvent(self, event) -> None:
        super().changeEvent(event)
        if event.type() == QEvent.Type.PaletteChange and hasattr(self, "log"):
            self._refresh()  # the muted colour of acknowledged alarms follows the palette

    def _acknowledge_selected(self) -> None:
        item = self.list_widget.currentItem()
        if item is not None:
            self._monitor.acknowledge(item.data(Qt.ItemDataRole.UserRole))

    def _refresh(self) -> None:
        current = self.list_widget.currentItem()
        selected = None if current is None else current.data(Qt.ItemDataRole.UserRole)
        self.list_widget.blockSignals(True)  # rebuild quietly, then update the buttons once
        self.list_widget.clear()
        for index, alarm in reversed(list(enumerate(self.log.alarms))):
            item = QListWidgetItem(format_alarm(alarm))
            item.setData(Qt.ItemDataRole.UserRole, index)
            if alarm.acknowledged:
                item.setForeground(QBrush(self.palette().color(QPalette.ColorRole.PlaceholderText)))
            else:
                font = QFont(item.font())
                font.setBold(True)
                item.setFont(font)
                item.setBackground(QBrush(_tinted(STATE_COLOURS[alarm.severity], 0.25)))
            self.list_widget.addItem(item)
            if index == selected:
                self.list_widget.setCurrentItem(item)
        self.list_widget.blockSignals(False)
        if selected is None:
            self._select_newest_unacknowledged()
        unacknowledged = self.log.unacknowledged_count
        self.summary_label.setText(f"{unacknowledged} new" if unacknowledged else "No new alarms")
        self._refresh_buttons()

    def _select_newest_unacknowledged(self) -> None:
        for row in range(self.list_widget.count()):
            item = self.list_widget.item(row)
            if not self._alarm_of(item).acknowledged:
                self.list_widget.setCurrentItem(item)
                return

    def _refresh_buttons(self) -> None:
        item = self.list_widget.currentItem()
        selected = item is not None and not self._alarm_of(item).acknowledged
        self.acknowledge_button.setEnabled(selected)

    def _alarm_of(self, item: QListWidgetItem) -> Alarm:
        return self.log.alarms[item.data(Qt.ItemDataRole.UserRole)]


def _tinted(colour: str, alpha: float) -> QColor:
    tint = QColor(colour)
    tint.setAlphaF(alpha)
    return tint
