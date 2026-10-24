"""The Validation tab of the Dashboard: error metrics and fault-detection scores for one run config.

Run validation builds its own headless batch from the config that was applied last. The batch
runs on a worker thread and the result comes back to the UI thread as a signal, so the window
stays responsive and the live run is never touched. While the batch runs the button is disabled
and a progress bar shows. Export buttons write the samples and the metrics to files the user picks.
"""

import logging
from pathlib import Path

from PyQt6.QtCore import QObject, QThread, Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pvysics.export import write_samples_csv, write_validation_csv
from pvysics.faults import FaultKind
from pvysics.gui.palette import STATE_COLOURS
from pvysics.gui.process_view import PLACEHOLDER
from pvysics.gui.ui_helpers import role_label, set_property
from pvysics.gui.metric_strip import MetricStrip
from pvysics.gui.palette import LIGHT, Palette
from pvysics.run import RunConfig, State
from pvysics.validation import NEAR_ZERO_W, STATE_ORDER, ValidationReport, run_validation

log = logging.getLogger(__name__)

STRIP_TIP = (
    f"Night samples are excluded; MAPE also skips samples below {NEAR_ZERO_W:g} W.\n"
    "False alarms: healthy-run samples flagged, at your limits and at limits derived from the healthy run."
)
TRUTH_LABELS = ("Normal operation", "Fault")
TINT_ALPHA = 0.35
STALE_NOTE = "Setup changed since this run. Run validation again."

EMPTY_TEXT = "No results yet."


class ValidationWorker(QObject):
    """Runs one validation. It lives on a worker thread and reports back through its signals only."""

    succeeded = pyqtSignal(object)  # ValidationReport
    failed = pyqtSignal(str)

    def __init__(self, config: RunConfig) -> None:
        super().__init__()
        self._config = config

    def work(self) -> None:
        try:
            report = run_validation(self._config)
        except Exception as error:  # shown on screen; an exception must not die silently in the thread
            log.error("Validation failed: %s", error)
            self.failed.emit(str(error))
        else:
            metrics = report.metrics
            log.info(
                "Validation finished: MAE %.2f W, RMSE %.2f W, MAPE %.2f %%",
                metrics.mae_w,
                metrics.rmse_w,
                metrics.mape_pct,
            )
            self.succeeded.emit(report)


class ValidationView(QWidget):
    """Runs and shows the validation of the applied config, and exports its results."""

    def __init__(self, config: RunConfig, parent: QWidget | None = None, palette: Palette = LIGHT) -> None:
        super().__init__(parent)
        self._config = config
        self._report: ValidationReport | None = None
        self._thread: QThread | None = None
        self._worker: ValidationWorker | None = None
        self.strip = MetricStrip(
            [
                ("Accuracy on healthy data", [("mae", "MAE"), ("rmse", "RMSE"), ("mape", "MAPE")]),
                (
                    "Fault detection",
                    [
                        ("detection_rate", "Detection rate"),
                        ("mean_delay", "Mean delay"),
                        ("false_alarm_config", "False alarms"),
                        ("false_alarm_derived", "False alarms, derived limits"),
                    ],
                ),
            ],
            palette,
        )
        self.strip.setToolTip(STRIP_TIP)
        self._build()
        self._show_config()

    @property
    def is_running(self) -> bool:
        return self._thread is not None

    @property
    def report(self) -> ValidationReport | None:
        return self._report

    def set_config(self, config: RunConfig) -> None:
        """Use config for the next validation. A result for an older config is marked as stale."""
        self._config = config
        self._show_config()
        if self._report is not None and self._report.config is not config:  # identity: configs hold arrays
            self._say(STALE_NOTE)

    def start_validation(self) -> None:
        """Start the batch on a worker thread for the applied config. Does nothing while one is running."""
        if self.is_running:
            return
        log.info("Validation started: one healthy run and five fault runs")
        self._thread = QThread(self)
        self._worker = ValidationWorker(self._config)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.work)
        self._worker.succeeded.connect(self._on_succeeded)
        self._worker.failed.connect(self._on_failed)
        self._worker.succeeded.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)
        self._thread.finished.connect(self._on_thread_finished)
        self._thread.finished.connect(self._thread.deleteLater)
        self._set_busy(True)
        self._thread.start()

    def shutdown(self) -> None:
        """End a running validation before the window closes, so its thread is never destroyed while running.

        The UI thread blocks here until the batch returns (a few seconds at most). quit() is called
        directly because the queued quit from the worker could only be delivered by this blocked thread.
        """
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait()
            self._on_thread_finished()

    def _on_succeeded(self, report: ValidationReport) -> None:
        self._report = report
        self._show_report(report)
        self._say("")  # the results are the message

    def _on_failed(self, message: str) -> None:
        self._say(f"Validation failed: {message}")

    def _on_thread_finished(self) -> None:
        self._thread = None
        self._worker = None
        self._set_busy(False)

    def _set_busy(self, busy: bool) -> None:
        self.run_button.setEnabled(not busy)
        self.progress.setVisible(busy)
        for button in (self.export_samples_button, self.export_metrics_button):
            button.setEnabled(not busy and self._report is not None)
        if busy:
            self._say("Running a healthy run and five fault runs...")

    def _show_config(self) -> None:
        config = self._config
        thresholds = config.thresholds
        self.config_label.setText(
            f"{config.profile.name or 'unnamed'}, {config.datasheet.name}, seed {config.seed}, "
            f"warning {thresholds.warning_pct:.2f} %, abnormal {thresholds.abnormal_pct:.2f} %"
        )

    def _show_report(self, report: ValidationReport) -> None:
        self.results.setVisible(True)
        self.empty_label.setVisible(False)
        metrics = report.metrics
        self.strip.set_values(
            {
                "mae": f"{metrics.mae_w:.2f} W",
                "rmse": f"{metrics.rmse_w:.2f} W",
                "mape": f"{metrics.mape_pct:.2f} %",
            }
        )
        for row in range(len(TRUTH_LABELS)):
            for column, state in enumerate(STATE_ORDER):
                count = report.confusion.count(row == 1, state)
                item = _read_only_item(str(count))
                tint = _confusion_tint(is_fault=row == 1, state=state, count=count)
                if tint is not None:
                    item.setBackground(QBrush(tint))
                self.confusion_table.setItem(row, column, item)
        for row, score in enumerate(report.faults):
            detected = score.delay_s is not None
            delay = PLACEHOLDER if score.delay_s is None else f"{score.delay_s:.0f} s"
            rate = PLACEHOLDER if score.detection_rate is None else f"{score.detection_rate * 100:.1f} %"
            result = _read_only_item("Detected" if detected else "Missed")
            result.setBackground(QBrush(_tinted(STATE_COLOURS[State.NORMAL if detected else State.ABNORMAL])))
            self.fault_table.setItem(row, 0, _read_only_item(score.kind.value))
            self.fault_table.setItem(row, 1, result)
            self.fault_table.setItem(row, 2, _read_only_item(delay))
            self.fault_table.setItem(row, 3, _read_only_item(rate))
        mean = PLACEHOLDER if report.mean_delay_s is None else f"{report.mean_delay_s:.0f} s"
        self.strip.set_values(
            {
                "mae": f"{metrics.mae_w:.2f} W",
                "rmse": f"{metrics.rmse_w:.2f} W",
                "mape": f"{metrics.mape_pct:.2f} %",
                "mean_delay": mean,
                "detection_rate": _percent(report.detection_rate),
                "false_alarm_config": f"{report.false_alarm_rate * 100:.1f} %",
                "false_alarm_derived": f"{report.false_alarm_rate_derived * 100:.1f} %",
            }
        )

    def _export_samples(self) -> None:
        report = self._report
        if report is None:
            return
        path = _choose_csv(self, "Export samples CSV")
        if path is None:
            return
        runs = {"healthy": report.healthy.samples}
        for fault_run in report.fault_runs:
            runs[fault_run.kind.value] = fault_run.result.samples
        try:
            write_samples_csv(path, runs)
        except OSError as error:
            self._export_failed(path, error)
            return
        log.info("Samples exported to %s", path)
        self._say(f"Samples written to {path}.")

    def _export_metrics(self) -> None:
        report = self._report
        if report is None:
            return
        path = _choose_csv(self, "Export metrics CSV")
        if path is None:
            return
        try:
            write_validation_csv(path, report)
        except OSError as error:
            self._export_failed(path, error)
            return
        log.info("Metrics exported to %s", path)
        self._say(f"Metrics written to {path}.")

    def _export_failed(self, path: Path, error: OSError) -> None:
        log.error("Export failed: could not write %s: %s", path.name, error)
        self._say(f"Could not write {path.name}: {error}")

    def _say(self, text: str) -> None:
        self.status_label.setText(text)
        self.status_label.setVisible(bool(text))

    def _on_run_clicked(self, *_args) -> None:
        self.start_validation()

    def _on_export_samples_clicked(self, *_args) -> None:
        self._export_samples()

    def _on_export_metrics_clicked(self, *_args) -> None:
        self._export_metrics()

    def _build(self) -> None:
        self.run_button = QPushButton("Run validation")
        set_property(self.run_button, "variant", "primary")
        self.run_button.setToolTip("Score the applied setup on a healthy run and on one run for each fault.")
        self.run_button.clicked.connect(self._on_run_clicked)
        self.export_samples_button = QPushButton("Export samples CSV...")
        self.export_samples_button.clicked.connect(self._on_export_samples_clicked)
        self.export_metrics_button = QPushButton("Export metrics CSV...")
        self.export_metrics_button.clicked.connect(self._on_export_metrics_clicked)
        for button in (self.export_samples_button, self.export_metrics_button):
            button.setEnabled(False)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)  # busy indicator: no known length
        self.progress.setVisible(False)
        self.status_label = role_label("", "muted")  # only shown when there is something to say
        self.status_label.setWordWrap(True)
        self.status_label.setVisible(False)
        self.config_label = role_label("", "muted")
        self.config_label.setWordWrap(True)
        self.empty_label = role_label(EMPTY_TEXT, "muted", Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setWordWrap(True)

        self.confusion_table = _table(
            len(TRUTH_LABELS), [state.value for state in STATE_ORDER], TRUTH_LABELS
        )
        self.fault_table = _table(len(FaultKind), ["Fault", "Result", "Detection delay", "Detection rate"])

        faults = _section("Each fault", self.fault_table)

        confusion = _section("Twin against truth", self.confusion_table)

        # The figures across the top, then the per-fault detail and the confusion matrix side by side.
        grid = QHBoxLayout()
        grid.setSpacing(24)
        grid.addWidget(faults, 1)
        grid.addWidget(confusion, 1)

        # The results appear with the first report; until then the empty state says what the button does.
        self.results = QWidget()
        results_layout = QVBoxLayout(self.results)
        results_layout.setContentsMargins(0, 0, 0, 0)
        results_layout.addWidget(self.strip)
        results_layout.addLayout(grid)
        results_layout.addStretch(1)
        self.results.setVisible(False)

        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.addWidget(self.empty_label, 1)
        body_layout.addWidget(self.results)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(body)

        # The header stays put while the results scroll: the title, the scored config and the actions.
        title_row = QHBoxLayout()
        title_row.addWidget(role_label("Validation", "title"))
        title_row.addStretch(1)
        title_row.addWidget(self.export_samples_button)
        title_row.addWidget(self.export_metrics_button)
        title_row.addWidget(self.run_button)
        status_row = QHBoxLayout()
        status_row.addWidget(self.status_label, 1)
        status_row.addWidget(self.progress, 1)

        root = QVBoxLayout(self)
        root.addLayout(title_row)
        root.addWidget(self.config_label)
        root.addLayout(status_row)
        root.addWidget(scroll, 1)


def _section(title: str, body: QWidget) -> QWidget:
    """A heading over a table, without a box around them."""
    section = QWidget()
    layout = QVBoxLayout(section)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.addWidget(role_label(title.upper(), "section"))
    layout.addWidget(body)
    layout.addStretch(1)
    return section


def _tinted(colour: str) -> QColor:
    tint = QColor(colour)
    tint.setAlphaF(TINT_ALPHA)
    return tint


def _confusion_tint(is_fault: bool, state: State, count: int) -> QColor | None:
    """Green where the twin was right, red where it was wrong, nothing where the count is zero."""
    if count == 0:
        return None
    right = state is not State.NORMAL if is_fault else state is State.NORMAL
    return _tinted(STATE_COLOURS[State.NORMAL if right else State.ABNORMAL])


def _percent(fraction: float | None) -> str:
    return PLACEHOLDER if fraction is None else f"{fraction * 100:.1f} %"


def _read_only_item(text: str) -> QTableWidgetItem:
    item = QTableWidgetItem(text)
    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
    return item


def _table(row_count: int, column_labels, row_labels=()) -> QTableWidget:
    table = QTableWidget(row_count, len(column_labels))
    table.setHorizontalHeaderLabels(list(column_labels))
    if row_labels:
        table.setVerticalHeaderLabels(list(row_labels))
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    if not row_labels:
        table.verticalHeader().setVisible(False)
    table.resizeRowsToContents()
    rows_height = sum(table.rowHeight(row) for row in range(row_count))
    table.setFixedHeight(table.horizontalHeader().sizeHint().height() + rows_height + 2 * table.frameWidth() + 2)
    return table


def _choose_csv(parent: QWidget, title: str) -> Path | None:
    path, _filter = QFileDialog.getSaveFileName(parent, title, "", "CSV files (*.csv);;All files (*)")
    if not path:
        return None
    file = Path(path)
    if file.suffix.lower() != ".csv":
        file = Path(f"{path}.csv")
    return file
