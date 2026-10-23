"""The Validation tab of the Dashboard: error metrics and fault-detection scores for one run config.

Run validation builds its own headless batch from the config that was applied last. The batch
runs on a worker thread and the result comes back to the UI thread as a signal, so the window
stays responsive and the live run is never touched. While the batch runs the button is disabled
and a progress bar shows. Export buttons write the samples and the metrics to files the user picks.
"""

import logging
from pathlib import Path

from PyQt6.QtCore import QObject, QThread, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pvysics.export import write_samples_csv, write_validation_csv
from pvysics.faults import FaultKind
from pvysics.gui.process_view import PLACEHOLDER
from pvysics.gui.widgets import KpiTile
from pvysics.run import POWER_FLOOR_W, RunConfig
from pvysics.validation import NEAR_ZERO_W, STATE_ORDER, ValidationReport, run_validation

log = logging.getLogger(__name__)

NIGHT_NOTE = (
    "Night-time samples are excluded: only daylight samples count, where predicted power is at least "
    f"{POWER_FLOOR_W:g} W. MAPE also skips daylight samples where measured power is below {NEAR_ZERO_W:g} W."
)
TRUTH_LABELS = ("Normal operation", "Fault")
STALE_NOTE = "The applied config has changed since this validation. Run validation again to score it."


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

    def __init__(self, config: RunConfig, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config = config
        self._report: ValidationReport | None = None
        self._thread: QThread | None = None
        self._worker: ValidationWorker | None = None
        self.tiles = {"mae": KpiTile("MAE"), "rmse": KpiTile("RMSE"), "mape": KpiTile("MAPE")}
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
            self.status_label.setText(STALE_NOTE)

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
        self.status_label.setText("Validation finished for the applied config.")

    def _on_failed(self, message: str) -> None:
        self.status_label.setText(f"Validation failed: {message}")

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
            self.status_label.setText("Running validation: one healthy run and five fault runs. Please wait.")

    def _show_config(self) -> None:
        config = self._config
        thresholds = config.thresholds
        self.config_label.setText(
            f"Scored config: profile {config.profile.name or 'unnamed'}, module {config.datasheet.name}, "
            f"seed {config.seed}, warning {thresholds.warning_pct:.2f} %, abnormal {thresholds.abnormal_pct:.2f} %"
        )

    def _show_report(self, report: ValidationReport) -> None:
        metrics = report.metrics
        self.tiles["mae"].set_value(f"{metrics.mae_w:.2f} W")
        self.tiles["rmse"].set_value(f"{metrics.rmse_w:.2f} W")
        self.tiles["mape"].set_value(f"{metrics.mape_pct:.2f} %")
        self.sample_label.setText(
            f"MAE and RMSE use {metrics.sample_count} daylight samples. "
            f"MAPE uses {metrics.mape_sample_count} of them, those with measured power at or above "
            f"{NEAR_ZERO_W:g} W."
        )
        for row, truth in enumerate(TRUTH_LABELS):
            for column, state in enumerate(STATE_ORDER):
                count = report.confusion.count(row == 1, state)
                self.confusion_table.setItem(row, column, _read_only_item(str(count)))
        for row, score in enumerate(report.faults):
            delay = PLACEHOLDER if score.delay_s is None else f"{score.delay_s:.0f} s"
            rate = PLACEHOLDER if score.detection_rate is None else f"{score.detection_rate * 100:.1f} %"
            self.fault_table.setItem(row, 0, _read_only_item(score.kind.value))
            self.fault_table.setItem(row, 1, _read_only_item(delay))
            self.fault_table.setItem(row, 2, _read_only_item(rate))
        mean = PLACEHOLDER if report.mean_delay_s is None else f"{report.mean_delay_s:.0f} s"
        self.mean_delay_label.setText(mean)
        self.detection_rate_label.setText(_percent(report.detection_rate))
        derived = report.derived_thresholds
        thresholds = report.config.thresholds
        self.false_alarm_config_label.setText(
            f"{report.false_alarm_rate * 100:.1f} % at warning {thresholds.warning_pct:.2f} %, "
            f"abnormal {thresholds.abnormal_pct:.2f} %"
        )
        self.false_alarm_derived_label.setText(
            f"{report.false_alarm_rate_derived * 100:.1f} % at warning {derived.warning_pct:.2f} %, "
            f"abnormal {derived.abnormal_pct:.2f} %"
        )
        self.status_label.setText("Validation finished for the applied config.")

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
        self.status_label.setText(f"Samples written to {path}.")

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
        self.status_label.setText(f"Metrics written to {path}.")

    def _export_failed(self, path: Path, error: OSError) -> None:
        log.error("Export failed: could not write %s: %s", path.name, error)
        self.status_label.setText(f"Could not write {path.name}: {error}")

    def _on_run_clicked(self, *_args) -> None:
        self.start_validation()

    def _on_export_samples_clicked(self, *_args) -> None:
        self._export_samples()

    def _on_export_metrics_clicked(self, *_args) -> None:
        self._export_metrics()

    def _build(self) -> None:
        self.run_button = QPushButton("Run validation")
        self.run_button.clicked.connect(self._on_run_clicked)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)  # busy indicator: no known length
        self.progress.setVisible(False)
        self.status_label = QLabel("Press Run validation to score the applied config.")
        self.status_label.setWordWrap(True)
        self.config_label = QLabel()
        self.config_label.setWordWrap(True)
        self.note_label = QLabel(NIGHT_NOTE)
        self.note_label.setWordWrap(True)
        self.sample_label = QLabel()
        self.sample_label.setWordWrap(True)

        self.confusion_table = _table(
            len(TRUTH_LABELS), [state.value for state in STATE_ORDER], TRUTH_LABELS
        )
        self.fault_table = _table(
            len(FaultKind), ["Fault", "Detection delay", "Detection rate"]
        )

        self.mean_delay_label = QLabel(PLACEHOLDER)
        self.detection_rate_label = QLabel(PLACEHOLDER)
        self.false_alarm_config_label = QLabel(PLACEHOLDER)
        self.false_alarm_derived_label = QLabel(PLACEHOLDER)
        self.export_samples_button = QPushButton("Export samples CSV...")
        self.export_samples_button.clicked.connect(self._on_export_samples_clicked)
        self.export_metrics_button = QPushButton("Export metrics CSV...")
        self.export_metrics_button.clicked.connect(self._on_export_metrics_clicked)
        for button in (self.export_samples_button, self.export_metrics_button):
            button.setEnabled(False)

        run_row = QHBoxLayout()
        run_row.addWidget(self.run_button)
        run_row.addWidget(self.progress, 1)

        tiles = QHBoxLayout()
        for tile in self.tiles.values():
            tiles.addWidget(tile)

        confusion_box = QGroupBox("Fault detection: confusion matrix, daylight samples (rows: truth, columns: estimated state)")
        confusion = QVBoxLayout(confusion_box)
        confusion.addWidget(self.confusion_table)
        confusion.addStretch(1)

        performance_box = QGroupBox("Detection performance")
        performance = QVBoxLayout(performance_box)
        performance.addWidget(self.fault_table)
        summary = QFormLayout()
        summary.addRow("Mean detection delay", self.mean_delay_label)
        summary.addRow("Detection rate", self.detection_rate_label)
        summary.addRow("False-alarm rate, config thresholds", self.false_alarm_config_label)
        summary.addRow("False-alarm rate, derived thresholds", self.false_alarm_derived_label)
        performance.addLayout(summary)

        exports = QHBoxLayout()
        exports.addStretch(1)
        exports.addWidget(self.export_samples_button)
        exports.addWidget(self.export_metrics_button)

        charts = QHBoxLayout()
        charts.addWidget(confusion_box, 1)
        charts.addWidget(performance_box, 1)

        root = QVBoxLayout(self)
        root.addWidget(self.note_label)
        root.addWidget(self.config_label)
        root.addLayout(run_row)
        root.addWidget(self.status_label)
        root.addLayout(tiles)
        root.addWidget(self.sample_label)
        root.addLayout(charts, 1)
        root.addLayout(exports)


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
