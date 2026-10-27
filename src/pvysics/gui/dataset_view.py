"""The Dataset Analysis view: import a CSV of the plant's readings, score the twin on it, replay it.

The view mirrors the Validation view: the analysis runs on a worker thread (the headless
analyse_dataset in pvysics/dataset.py), so the window stays responsive and the live run is
never touched. A report shows as figures, a deviation chart and an estimated-versus-
actual scatter, and can be exported as one CSV. Replay on Dashboard sends the report's Samples
through the session, so every window shows the dataset as if it were a run.
"""

import logging
from pathlib import Path

from PyQt6.QtCore import QObject, QThread, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

import pyqtgraph as pg

from pvysics.dataset import (
    DatasetError,
    DatasetReport,
    DatasetStore,
    Measurements,
    analyse_dataset,
    read_measurement_file,
    write_template,
)
from pvysics.export import write_dataset_analysis_csv
from pvysics.gui.metric_strip import PLACEHOLDER, Group, MetricStrip, Tile
from pvysics.gui.palette import LIGHT, Palette
from pvysics.gui.process_view import format_number
from pvysics.gui.theme import style_plot
from pvysics.gui.ui_helpers import CompactPlot, role_label, set_property
from pvysics.run import RunConfig

log = logging.getLogger(__name__)

STRIP_TIP = (
    "The figures are over daylight rows, estimated power at or above 5 W: night rows never\n"
    "dilute them. MAPE also skips rows with actual power below 5 W. MBE is the mean of\n"
    "estimated minus actual power: positive means the twin over-predicts."
)
NO_DATASET = "No dataset analysed yet."
IMPORT_TITLE = "Import measurements"
IMPORT_FILTER = "Measurement files (*.csv *.xlsx);;CSV files (*.csv);;Excel workbooks (*.xlsx);;All files (*)"
TEMPLATE_TITLE = "Save the template"
TEMPLATE_FILTER = "Excel workbook (*.xlsx);;CSV file (*.csv)"
EXPORT_TITLE = "Export analysis CSV"
IMPORT_PENDING = "Import a file of measurements first."


class StripStack(QWidget):
    """One MetricStrip per group, stacked, so each group has the whole width. Twelve figures in one row
    would not fit beside the sidebar. It reads and writes figures by key, as a single strip does."""

    def __init__(self, groups: list[Group], palette: Palette, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._strips = [MetricStrip([group], palette) for group in groups]
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        for strip in self._strips:
            layout.addWidget(strip)

    def value(self, key: str) -> str:
        for strip in self._strips:
            try:
                return strip.value(key)
            except KeyError:
                continue
        raise KeyError(key)

    def set_values(self, values: dict[str, str]) -> None:
        for strip in self._strips:
            strip.set_values(values)  # each shows only its own figures

    def clear(self) -> None:
        for strip in self._strips:
            strip.clear()

    def set_palette(self, palette: Palette) -> None:
        for strip in self._strips:
            strip.set_palette(palette)

    def setToolTip(self, text: str) -> None:  # noqa: N802 (Qt's name)
        super().setToolTip(text)
        for strip in self._strips:
            strip.setToolTip(text)


class DatasetWorker(QObject):
    """Scores one dataset on a worker thread and reports back through its signals only."""

    succeeded = pyqtSignal(object)  # DatasetReport
    failed = pyqtSignal(str)

    def __init__(self, dataset: Measurements, config: RunConfig) -> None:
        super().__init__()
        self._dataset = dataset
        self._config = config

    def work(self) -> None:
        try:
            report = analyse_dataset(self._dataset, self._config)
        except Exception as error:  # shown on screen; an exception must not die silently in the thread
            log.error("Dataset analysis failed: %s", error)
            self.failed.emit(str(error))
        else:
            metrics = report.metrics
            log.info(
                "Dataset analysed: %s, %d rows, MAE %.2f W, MAPE %.2f %%",
                report.name,
                metrics.row_count,
                metrics.mae_w,
                metrics.mape_pct,
            )
            self.succeeded.emit(report)


class DatasetAnalysisView(QWidget):
    """The datasets of the store, and what the twin scored on the chosen one."""

    replay_requested = pyqtSignal(object)  # DatasetReport, for the session to replay

    def __init__(
        self,
        config: RunConfig,
        store: DatasetStore,
        palette: Palette = LIGHT,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._config = config
        self._store = store
        self._report: DatasetReport | None = None
        self._thread: QThread | None = None
        self._worker: DatasetWorker | None = None
        self.strip = StripStack(
            [
                Group(
                    "The dataset",
                    [
                        Tile("samples", "Samples"),
                        Tile("g_mean", "Mean G"),
                        Tile("actual_mean", "Mean actual P"),
                        Tile("estimated_mean", "Mean estimated P"),
                    ],
                    spread=True,
                ),
                Group(
                    "Accuracy",
                    [Tile("mae", "MAE"), Tile("rmse", "RMSE"), Tile("mape", "MAPE"), Tile("mbe", "MBE")],
                    spread=True,
                ),
                Group(
                    "Deviation and states",
                    [
                        Tile("deviation_mean", "Mean deviation"),
                        Tile("normal", "Normal"),
                        Tile("warning", "Warning"),
                        Tile("potential_fault", "Abnormal"),
                    ],
                    spread=True,
                ),
            ],
            palette,
        )
        self.strip.setToolTip(STRIP_TIP)
        self._build()
        self.apply_palette(palette)
        self.refresh_datasets()

    @property
    def is_running(self) -> bool:
        return self._thread is not None

    @property
    def report(self) -> DatasetReport | None:
        return self._report

    @property
    def dataset_name(self) -> str:
        """The dataset the combo has chosen, or an empty string for none."""
        return self.dataset_box.currentText()

    def set_config(self, config: RunConfig) -> None:
        """Score the next analysis with config. A result for an older config gets a stale note."""
        if self._config is config:
            return
        self._config = config
        if self._report is not None and self._report.config is not config:  # identity: configs hold arrays
            self._say("The setup changed. Analyse again to score the dataset with it.")

    def refresh_datasets(self) -> None:
        """Reread the store's names, keeping the chosen one when it survives."""
        chosen = self.dataset_name
        self.dataset_box.clear()
        self.dataset_box.addItems(self._store.names())
        index = self.dataset_box.findText(chosen)
        if index >= 0:
            self.dataset_box.setCurrentIndex(index)
        self._refresh_buttons()

    def import_file(self, path: Path) -> None:
        """Read a measurements CSV into the store and choose it. Errors are reported on screen."""
        displayed = getattr(path, "name", str(path))
        try:
            dataset = read_measurement_file(Path(path))
            name = self._store.save(path.stem, dataset)
        except (DatasetError, OSError, UnicodeError) as error:
            log.error("Import failed: could not import %s: %s", displayed, error)
            self._say(f"Could not import {displayed}: {error}")
            return
        log.info("Dataset imported: %s (%d rows)", name, len(dataset.timestamps))
        self.refresh_datasets()
        index = self.dataset_box.findText(name)
        if index >= 0:
            self.dataset_box.setCurrentIndex(index)
        self._say(f"Imported '{name}' ({len(dataset.timestamps)} rows). Analyse to score it.")

    def shutdown(self) -> None:
        """End a running analysis before the window closes, so its thread is never destroyed while running."""
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait()
            self._on_thread_finished()

    def clear_report(self) -> None:
        """Forget the report: back to the empty state (a deleted dataset leaves nothing to show)."""
        self._report = None
        self.strip.clear()
        self.score_label.clear()
        self._deviation_curve.setData([], [])
        self._estimated_curve.setData([], [])
        self._reference_curve.setData([], [])
        self._show_report_view(False)
        self._refresh_buttons()

    def apply_palette(self, palette: Palette) -> None:
        self.strip.set_palette(palette)
        for plot in (self.deviation_plot, self.scatter_plot):
            style_plot(plot, palette)
        self._deviation_curve.setPen(pg.mkPen(palette.deviation, width=2))
        self._estimated_curve.setSymbolBrush(pg.mkBrush(palette.measured))
        self._reference_curve.setPen(pg.mkPen(palette.muted_text, style=Qt.PenStyle.DashLine))

    def _build(self) -> None:
        self.dataset_box = QComboBox(self)
        self.dataset_box.setMinimumContentsLength(12)  # a name row as wide as about a dozen letters
        self.dataset_box.currentIndexChanged.connect(self._refresh_buttons)

        self.template_button = QPushButton("TEMPLATE…")
        self.template_button.setToolTip("Save an empty CSV or Excel file with the columns to fill in, and examples.")
        self.template_button.clicked.connect(self._on_template_clicked)
        self.import_button = QPushButton("IMPORT FILE…")
        self.import_button.setToolTip("Read a CSV or Excel file of the plant's readings into the dataset store.")
        self.import_button.clicked.connect(self._on_import_clicked)
        self.analyse_button = QPushButton("ANALYSE")
        self.analyse_button.setToolTip("Score the chosen dataset with the twin, at the current setup.")
        self.analyse_button.clicked.connect(self._on_analyse_clicked)
        self.replay_button = QPushButton("REPLAY ON DASHBOARD")
        self.replay_button.setToolTip("Show this dataset's analysed Samples on every page, as the run.")
        self.replay_button.clicked.connect(self._on_replay_clicked)
        self.export_button = QPushButton("EXPORT ANALYSIS CSV")
        self.export_button.setToolTip("Write every analysed row and the metrics to a file.")
        self.export_button.clicked.connect(self._on_export_clicked)
        self.delete_button = QPushButton("DELETE DATASET")
        self.delete_button.setToolTip("Remove the chosen dataset from the store.")
        self.delete_button.clicked.connect(self._on_delete_clicked)
        for button in (self.template_button, self.import_button, self.analyse_button, self.replay_button, self.export_button, self.delete_button):
            set_property(button, "variant", "primary")

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)  # busy indicator: no known length
        self.progress.setVisible(False)
        self.status_label = role_label("", "muted")  # only shown when there is something to say
        self.status_label.setWordWrap(True)
        self.score_label = role_label("", "muted")  # the setup the report was scored with
        self.score_label.setWordWrap(True)
        self.empty_label = role_label(NO_DATASET, "muted", Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setWordWrap(True)

        self.deviation_plot = _plot("Deviation (%)", "Sample")
        self.scatter_plot = _plot("Estimated (W)", "Actual (W)")
        self._deviation_curve = self.deviation_plot.plot([], [], pen=pg.mkPen(LIGHT.deviation, width=2))
        self._estimated_curve = self.scatter_plot.plot(
            [], [], pen=None, symbol="o", symbolSize=7, symbolPen=None, symbolBrush=pg.mkBrush(LIGHT.measured)
        )
        self._reference_curve = self.scatter_plot.plot(
            [], [], pen=pg.mkPen(LIGHT.muted_text, style=Qt.PenStyle.DashLine)
        )

        results = QWidget()
        results_layout = QVBoxLayout(results)
        results_layout.setContentsMargins(0, 0, 0, 0)
        results_layout.addWidget(self.strip)
        results_layout.addWidget(self.score_label)
        charts = QHBoxLayout()
        charts.setSpacing(24)
        charts.addWidget(_section("Power deviation", self.deviation_plot), 1)
        charts.addWidget(_section("Estimated vs actual power", self.scatter_plot), 1)
        results_layout.addLayout(charts)
        results_layout.addStretch(1)
        self.results = results
        self.results.setVisible(False)

        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.addWidget(self.empty_label, 1)
        body_layout.addWidget(self.results)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(body)

        dataset_row = QHBoxLayout()
        dataset_row.addWidget(role_label("Dataset:", "cardSub"))
        dataset_row.addWidget(self.dataset_box)
        dataset_row.addStretch(1)
        dataset_row.addWidget(self.template_button)
        dataset_row.addWidget(self.import_button)
        dataset_row.addWidget(self.analyse_button)
        dataset_row.addWidget(self.replay_button)
        dataset_row.addWidget(self.export_button)
        dataset_row.addWidget(self.delete_button)
        status_row = QHBoxLayout()
        status_row.addWidget(self.status_label, 1)
        status_row.addWidget(self.progress, 1)

        root = QVBoxLayout(self)
        root.addLayout(dataset_row)
        root.addLayout(status_row)
        root.addWidget(scroll, 1)

    def _say(self, text: str) -> None:
        """A one-line message to the user: the status line says it, or hides for nothing."""
        self.status_label.setText(text)
        self.status_label.setVisible(bool(text))

    def _on_import_clicked(self, *_args) -> None:
        path, _filter = QFileDialog.getOpenFileName(self, IMPORT_TITLE, "", IMPORT_FILTER)
        if path:
            self.import_file(Path(path))

    def save_template(self, path: Path) -> None:
        """Write the upload template to path (.csv or .xlsx). Errors are reported on screen."""
        try:
            write_template(path)
        except (DatasetError, OSError) as error:
            log.error("Template not written: %s: %s", path.name, error)
            self._say(f"Could not write {path.name}: {error}")
            return
        log.info("Template saved to %s", path)
        self._say(f"Template saved to {path}. Fill it in, then import it.")

    def _on_template_clicked(self, *_args) -> None:
        path, chosen = QFileDialog.getSaveFileName(self, TEMPLATE_TITLE, "pvysics-dataset-template.xlsx", TEMPLATE_FILTER)
        if not path:
            return
        file = Path(path)
        if file.suffix.lower() not in (".csv", ".xlsx"):
            file = Path(f"{path}.csv" if "csv" in chosen.lower() else f"{path}.xlsx")
        self.save_template(file)

    def _on_analyse_clicked(self, *_args) -> None:
        if self.is_running:
            return
        name = self.dataset_name
        if not name:
            self._say(IMPORT_PENDING)
            return
        try:
            dataset = self._store.read(name)
        except (DatasetError, OSError) as error:
            self._say(f"Could not read '{name}': {error}")
            return
        log.info("Dataset analysis started: %s", name)
        self._thread = QThread(self)
        self._worker = DatasetWorker(dataset, self._config)
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

    def _on_replay_clicked(self, *_args) -> None:
        if self._report is None:
            self._say("Analyse a dataset first.")
            return
        self.replay_requested.emit(self._report)
        self._say(f"Replayed '{self._report.name}' on the Dashboard.")

    def _on_export_clicked(self, *_args) -> None:
        if self._report is None:
            return
        path, _filter = QFileDialog.getSaveFileName(self, EXPORT_TITLE, "", "CSV files (*.csv);;All files (*)")
        if not path:
            return
        file = Path(path)
        if file.suffix.lower() != ".csv":
            file = Path(f"{path}.csv")
        try:
            write_dataset_analysis_csv(file, self._report)
        except OSError as error:
            log.error("Export failed: could not write %s: %s", file.name, error)
            self._say(f"Could not write {file.name}: {error}")
            return
        log.info("Analysis exported to %s", file)
        self._say(f"Analysis written to {file}.")

    def _on_delete_clicked(self, *_args) -> None:
        name = self.dataset_name
        if not name:
            self._say(IMPORT_PENDING)
            return
        try:
            self._store.delete(name)
        except (DatasetError, OSError) as error:
            self._say(f"Could not delete '{name}': {error}")
            return
        log.info("Dataset deleted: %s", name)
        if self._report is not None and self._report.name == name:
            self.clear_report()
        self.dataset_box.removeItem(self.dataset_box.findText(name))
        self._refresh_buttons()
        self._say(f"Dataset '{name}' deleted.")

    def _on_succeeded(self, report: DatasetReport) -> None:
        self._report = report
        self._show_report()
        self._refresh_buttons()  # this or _on_thread_finished can land first; both must end enabled
        self._say("")  # the results are the message

    def _on_failed(self, message: str) -> None:
        self._say(f"Analysis failed: {message}")

    def _on_thread_finished(self) -> None:
        self._thread = None
        self._worker = None
        self._set_busy(False)

    def _set_busy(self, busy: bool) -> None:
        if busy:
            self.progress.setVisible(True)
            self.analyse_button.setEnabled(False)
            self.delete_button.setEnabled(False)
            self.replay_button.setEnabled(False)
            self.export_button.setEnabled(False)
            self._say("Scoring the dataset with the twin...")
        else:
            self.progress.setVisible(False)
            self._refresh_buttons()

    def _refresh_buttons(self) -> None:
        chosen = bool(self.dataset_name)
        busy = self.is_running
        reported = self._report is not None
        self.analyse_button.setEnabled(chosen and not busy)
        self.delete_button.setEnabled(chosen and not busy)
        self.replay_button.setEnabled(reported and not busy)
        self.export_button.setEnabled(reported and not busy)

    def _show_report(self) -> None:
        self._show_report_view(True)
        report = self._report
        assert report is not None
        metrics = report.metrics
        samples = report.samples
        thresholds = report.config.thresholds
        self.score_label.setText(
            f"Scored against {report.config.datasheet.name}: warning {thresholds.warning_pct:g} %, "
            f"abnormal {thresholds.abnormal_pct:g} %"
        )
        self.strip.set_values(
            {
                "samples": f"{metrics.row_count}",
                "g_mean": f"{format_number(metrics.mean_irradiance_w_m2, 0)} W/m²",
                "actual_mean": f"{format_number(metrics.mean_actual_w, 1)} W",
                "estimated_mean": f"{format_number(metrics.mean_estimated_w, 1)} W",
                "mae": f"{metrics.mae_w:.2f} W",
                "rmse": f"{metrics.rmse_w:.2f} W",
                "mape": f"{metrics.mape_pct:.2f} %",
                "mbe": f"{format_number(metrics.mbe_w, 2, signed=True)} W",
                "deviation_mean": f"{format_number(metrics.mean_deviation_pct, 2, signed=True)} %",
                "normal": f"{metrics.normal_pct:.1f} %",
                "warning": f"{metrics.warning_pct:.1f} %",
                "potential_fault": f"{metrics.abnormal_pct:.1f} %",
            }
        )
        index = list(range(len(samples)))
        deviations = [sample.deviation_pct for sample in samples]
        actual = [sample.power_measured for sample in samples]
        estimated = [sample.power_predicted for sample in samples]
        self._deviation_curve.setData(index, deviations)
        self._estimated_curve.setData(actual, estimated)
        span = max(max(actual, default=0.0), max(estimated, default=0.0), 1.0) * 1.05
        self._reference_curve.setData([0.0, span], [0.0, span])

    def _show_report_view(self, report: bool) -> None:
        self.results.setVisible(report)
        self.empty_label.setVisible(not report)


def _plot(left: str, bottom: str) -> pg.PlotWidget:
    """A plain-axis chart in the palette's colours."""
    plot = CompactPlot()
    for side in ("left", "bottom"):
        plot.getAxis(side).enableAutoSIPrefix(False)
    plot.showGrid(x=True, y=True, alpha=0.3)
    plot.setLabel("left", left)
    plot.setLabel("bottom", bottom)
    plot.setMinimumHeight(240)
    return plot


def _section(title: str, body: QWidget) -> QWidget:
    """A bordered group with its title on the border, holding a chart."""
    section = QGroupBox(title)
    layout = QVBoxLayout(section)
    layout.addWidget(body)
    return section
