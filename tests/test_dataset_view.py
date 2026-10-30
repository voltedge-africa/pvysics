"""The Dataset Analysis page: import, analyse, replay on the Dashboard, export and delete."""

from dataclasses import replace

from PyQt6.QtWidgets import QFileDialog
import pytest

from pvysics.dataset import DATASETS_DIR_ENV, DatasetStore, parse_measurement_csv, write_template
from pvysics.gui.metric_strip import PLACEHOLDER
from pvysics.gui.session import Session
from pvysics.gui.simple_window import ANALYSIS
from pvysics.run import bundled_run_config

# A small daylight log in the raw logger spellings, so the header aliases get exercised too.
LOG_TEXT = (
    "Timestamp,G,Temp,PV Voltage,PV Current\n"
    "2025-01-15T10:00:00,812.5,35.2,29.6,7.9\n"
    "2025-01-15T10:01:00,820.1,35.4,29.6,8.1\n"
    "2025-01-15T10:02:00,827.4,35.5,29.5,8.0\n"
)


def make_window(qtbot, tmp_path, monkeypatch, config=None):
    """A Session whose datasets live in the test's temp dir, open on the Analysis page."""
    monkeypatch.setenv(DATASETS_DIR_ENV, str(tmp_path / "datasets"))
    session = Session(config=config or bundled_run_config(seed=1))
    window = session.open_simple()
    qtbot.addWidget(window)
    window.nav_buttons[ANALYSIS].click()
    return session, window


@pytest.fixture
def dataset_file(tmp_path):
    path = tmp_path / "day.csv"
    path.write_text(LOG_TEXT, encoding="utf-8")
    return path


def score(qtbot, view, dataset_file):
    view.import_file(dataset_file)
    assert view.dataset_name == "day"
    view.analyse_button.click()
    qtbot.waitUntil(lambda: view.report is not None and not view.is_running, timeout=15000)  # thread done too
    return view.report


def test_a_dataset_imports_scores_and_shows_the_numbers(qtbot, tmp_path, monkeypatch, dataset_file):
    _session, window = make_window(qtbot, tmp_path, monkeypatch)
    view = window.analysis_page.datasets

    report = score(qtbot, view, dataset_file)

    assert len(report.samples) == 3
    metrics = report.metrics
    assert metrics.row_count == 3
    assert metrics.sample_count == 3
    assert view.strip.value("mae") != PLACEHOLDER
    assert float(view.strip.value("mae").replace(" W", "")) >= 0.0
    assert view.analyse_button.isEnabled()
    assert not view.is_running


def test_analysing_the_same_dataset_twice_is_fine(qtbot, tmp_path, monkeypatch, dataset_file):
    _session, window = make_window(qtbot, tmp_path, monkeypatch)
    view = window.analysis_page.datasets

    first = score(qtbot, view, dataset_file)
    view.analyse_button.click()  # again with the same setup
    qtbot.waitUntil(lambda: not view.is_running, timeout=15000)

    assert view.report is not None
    assert first.metrics.mae_w == view.report.metrics.mae_w


def test_replay_shows_the_dataset_as_the_run(qtbot, tmp_path, monkeypatch, dataset_file):
    session, window = make_window(qtbot, tmp_path, monkeypatch)
    score(qtbot, window.analysis_page.datasets, dataset_file)

    window.analysis_page.datasets.replay_button.click()

    assert not session.playback.is_running  # the live run pauses during a replay
    assert "DAY" in window.dashboard_page.source_chip.text().upper()


def test_a_new_config_brings_the_simulated_plant_back(qtbot, tmp_path, monkeypatch, dataset_file):
    session, window = make_window(qtbot, tmp_path, monkeypatch)
    score(qtbot, window.analysis_page.datasets, dataset_file)
    window.analysis_page.datasets.replay_button.click()
    assert "DATASET" in window.dashboard_page.source_chip.text().upper()

    session.apply_config(replace(session.playback.config, seed=9))

    session.playback.pause()
    assert "SIMULATED PLANT" in window.dashboard_page.source_chip.text().upper()


def test_an_export_writes_the_analysis_csv(qtbot, tmp_path, monkeypatch, dataset_file):
    _session, window = make_window(qtbot, tmp_path, monkeypatch)
    view = window.analysis_page.datasets
    score(qtbot, view, dataset_file)
    out = tmp_path / "analysis.csv"
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(out), ""))
    )

    view.export_button.click()

    assert out.exists()
    rows = out.read_text(encoding="utf-8").strip().splitlines()
    assert rows[0].split(",")[:3] == ["timestamp", "irradiance_w_m2", "temperature_c"]
    assert "mpp_power_w" in rows[0].split(",")  # the theoretical maximum, next to the estimate
    assert any(row.startswith("metrics,MAE,") for row in rows)


def test_deleting_the_chosen_dataset_clears_the_page(qtbot, tmp_path, monkeypatch, dataset_file):
    session, window = make_window(qtbot, tmp_path, monkeypatch)
    view = window.analysis_page.datasets
    score(qtbot, view, dataset_file)

    view.delete_button.click()

    assert view.report is None
    assert view.dataset_name == ""
    store = DatasetStore(tmp_path / "datasets")
    assert store.names() == []
    assert "deleted" in view.status_label.text().lower()


def test_a_bad_file_is_reported_not_fatal(qtbot, tmp_path, monkeypatch):
    _session, window = make_window(qtbot, tmp_path, monkeypatch)
    view = window.analysis_page.datasets
    bad = tmp_path / "bad.csv"
    bad.write_text("Timestamp,G\n2025-01-15T10:00:00,10\n", encoding="utf-8")

    view.import_file(bad)

    assert "could not import" in view.status_label.text().lower()
    assert view.report is None


def test_a_stored_dataset_survives_the_page_and_the_launch(qtbot, tmp_path, monkeypatch, dataset_file):
    session, window = make_window(qtbot, tmp_path, monkeypatch)
    score(qtbot, window.analysis_page.datasets, dataset_file)

    store = DatasetStore(tmp_path / "datasets")
    dataset = store.read("day")

    assert len(dataset.timestamps) == 3
    assert session.datasets.names() == ["day"]


def test_a_parse_of_the_sample_log_gives_three_rows():
    dataset = parse_measurement_csv(LOG_TEXT, name="day")

    assert len(dataset.timestamps) == 3
    assert dataset.power[0] == dataset.voltage[0] * dataset.current[0]


def test_the_template_button_saves_a_template_that_imports_back(qtbot, tmp_path, monkeypatch):
    _session, window = make_window(qtbot, tmp_path, monkeypatch)
    view = window.analysis_page.datasets
    out = tmp_path / "pvysics-dataset-template.xlsx"
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(out), "Excel workbook (*.xlsx)"))
    )

    view.template_button.click()

    assert out.exists()
    assert "template saved" in view.status_label.text().lower()
    view.import_file(out)
    assert view.dataset_name == "pvysics-dataset-template"


def test_a_template_name_without_a_suffix_gets_the_chosen_type(qtbot, tmp_path, monkeypatch):
    _session, window = make_window(qtbot, tmp_path, monkeypatch)
    view = window.analysis_page.datasets
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(tmp_path / "plain"), "CSV file (*.csv)"))
    )

    view.template_button.click()

    assert (tmp_path / "plain.csv").exists()


def test_an_excel_file_imports_and_scores(qtbot, tmp_path, monkeypatch):
    _session, window = make_window(qtbot, tmp_path, monkeypatch)
    view = window.analysis_page.datasets
    path = tmp_path / "mine.xlsx"
    write_template(path)

    view.import_file(path)
    view.analyse_button.click()
    qtbot.waitUntil(lambda: view.report is not None and not view.is_running, timeout=15000)

    assert view.dataset_name == "mine"
    assert view.report.metrics.row_count == 5
