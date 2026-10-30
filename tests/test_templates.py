"""The ready-made template files in docs/templates must stay loadable by the app that asks users to fill them in."""

from pathlib import Path

import pytest

from pvysics.dataset import analyse_dataset, read_measurement_file
from pvysics.datasheet import load_datasheet
from pvysics.run import bundled_run_config
from pvysics.profile import csv_columns, guess_columns, parse_profile_table, read_profile_text

TEMPLATES = Path(__file__).resolve().parent.parent / "docs" / "templates"


@pytest.mark.parametrize("suffix", [".csv", ".xlsx"])
def test_the_dataset_template_loads(suffix):
    assert len(read_measurement_file(TEMPLATES / f"pvysics-dataset-template{suffix}").timestamps) == 5


@pytest.mark.parametrize("suffix", [".csv", ".xlsx"])
def test_the_shipped_dataset_template_scores_normal(suffix):
    dataset = read_measurement_file(TEMPLATES / f"pvysics-dataset-template{suffix}")

    report = analyse_dataset(dataset, bundled_run_config(seed=1))

    assert report.metrics.normal_pct == 100.0


@pytest.mark.parametrize("suffix", [".csv", ".xlsx"])
def test_the_weather_template_loads(suffix):
    text = read_profile_text(TEMPLATES / f"pvysics-weather-template{suffix}")

    assert len(parse_profile_table(text, guess_columns(csv_columns(text)), "weather").timestamps) == 24


@pytest.mark.parametrize("suffix", [".csv", ".xlsx"])
def test_the_datasheet_template_loads(suffix):
    assert load_datasheet(TEMPLATES / f"pvysics-datasheet-template{suffix}").ns == 60
