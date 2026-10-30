"""Datasets: the CSV parse, the twin analysis and the store. Headless."""

from dataclasses import replace

import numpy as np
import pytest

from pvysics.dataset import (
    DATASETS_DIR_ENV,
    DatasetError,
    DatasetStore,
    Measurements,
    analyse_dataset,
    default_datasets_dir,
    default_store,
    parse_measurement_csv,
)
from pvysics.run import POWER_FLOOR_W, State, Thresholds, bundled_run_config, run
from pvysics.single_diode import power_at_voltage, solve_curve
from pvysics.validation import error_metrics

CONFIG = bundled_run_config(seed=0)  # the bundled Durban day on the generic module
HEAD = ("timestamp", "irradiance_w_m2", "temperature_c", "voltage_v", "current_a")
HEAD_WITH_POWER = HEAD + ("actual_power_w",)


def csv_text(rows, header=HEAD) -> str:
    """Rows as tuples of str, int or float; a header of len(header) columns; a plain CSV text."""
    lines = [",".join(header)]
    for row in rows:
        values = [""] * len(header)
        for index, value in enumerate(row):
            values[index] = str(value)
        lines.append(",".join(values))
    return "\n".join(lines) + "\n"


def parse(rows, header=HEAD, name="demo") -> Measurements:
    return parse_measurement_csv(csv_text(rows, header), name=name)


def night_and_day_dataset():
    """Three daylight rows between two nights, power from voltage x current."""
    rows = [
        ("2025-01-15T05:00:00", 0.0, 20.0, 0.0, 0.0),  # night
        ("2025-01-15T07:00:00", 120.0, 22.0, 15.0, 1.4),
        ("2025-01-15T12:00:00", 890.0, 39.0, 29.9, 8.16),
        ("2025-01-15T17:00:00", 60.0, 28.0, 25.0, 0.9),
        ("2025-01-15T22:00:00", 0.0, 18.0, 0.0, 0.0),  # night
    ]
    return parse(rows, name="day"), rows


# parse tests


def test_parse_reads_the_common_column_names():
    dataset = parse(
        [
            ("2025-01-15T10:00:00", 800.0, 31.5, 29.9, 8.12),
            ("2025-01-15T10:01:00", 810.0, 31.6, 29.9, 8.2),
        ]
    )

    assert dataset.name == "demo"
    assert len(dataset.timestamps) == 2
    assert dataset.timestamps[1] == np.datetime64("2025-01-15T10:01:00", "s")
    assert dataset.irradiance[1] == pytest.approx(810.0)
    assert dataset.temperature[1] == pytest.approx(31.6)
    assert dataset.voltage[1] == pytest.approx(29.9)
    assert dataset.current[1] == pytest.approx(8.2)
    assert dataset.power[1] == pytest.approx(29.9 * 8.2)  # no power column: V x I


def test_parse_prefers_a_given_power_column():
    dataset = parse(
        [
            ("2025-01-15T10:00:00", 800.0, 31.5, 29.9, 8.12, 241.0),
            ("2025-01-15T10:01:00", 805.0, 31.5, 29.8, 8.15, 242.0),
        ],
        header=HEAD_WITH_POWER,
    )

    assert dataset.power[0] == pytest.approx(241.0)
    assert dataset.power[1] == pytest.approx(242.0)


def test_parse_accepts_real_log_noise_and_a_shadow():
    """A live logger's sensor noise can give tiny negative voltage or current at night."""
    dataset = parse(
        [
            ("2025-01-15T23:00:00", 0.0, 23.2, -0.004, 0.0),
            ("2025-01-15T23:01:00", 0.0, 23.2, 0.0, -0.0001),
        ]
    )
    assert dataset.power[0] == pytest.approx(0.0)
    assert dataset.power[1] == pytest.approx(0.0)


def test_parse_accepts_a_uneven_step_and_rejects_a_stall():
    dataset = parse(
        [
            ("2025-01-15T10:00:00", 100.0, 20.0, 20.0, 1.0),
            ("2025-01-15T10:05:04", 110.0, 20.1, 20.0, 1.1),  # a real log has gaps
        ]
    )
    assert dataset.timestamps[1] == np.datetime64("2025-01-15T10:05:04", "s")

    with pytest.raises(DatasetError, match="does not increase"):
        parse(
            [
                ("2025-01-15T10:00:00", 100.0, 20.0, 20.0, 1.0),
                ("2025-01-15T10:00:00", 110.0, 20.1, 20.0, 1.1),
            ]
        )


@pytest.mark.parametrize(
    ("rows", "header", "message"),
    [
        ([("2025-01-15T10:00:00", 10.0, 20.0), ("2025-01-15T10:01:00", 20.0, 20.0)], HEAD[:3], "actual power needs"),
        ([("yesterday", 10.0, 20.0, 20.0, 1.0), ("yesterday", 20.0, 20.0, 20.0, 1.1)], HEAD, "not an ISO"),
        ([("2025-01-15T10:00:00", -1.0, 20.0, 20.0, 1.0), ("2025-01-15T10:01:00", -1.0, 20.0, 20.0, 1.0)], HEAD, "irradiance is negative"),
        ([("night", 0.0, 20.0, 20.0, 1.0), ("night", 0.0, 20.0, 20.0, 1.1)], HEAD, "not an ISO"),
        ([("2025-01-15T10:00:00", -999.0, 20.0, 20.0, 1.0), ("2025-01-15T10:01:00", -999.0, 20.0, 20.0, 1.0)], HEAD, "-999"),
        ([("2025-01-15T10:00:00", 100.0, "", 20.0, 1.0), ("2025-01-15T10:01:00", 100.0, "", 20.0, 1.0)], HEAD, "temperature is missing"),
        ([("2025-01-15T10:00:00", 100.0, 20.0, 20.0, "abc"), ("2025-01-15T10:01:00", 100.0, 20.0, 20.0, "def")], HEAD, "not a number"),
        ([("2025-01-15T10:00:00", 100.0, 20.0, 20.0, 1.0), ("2025-01-15T10:01:00", 100.0, 20.0, 20.0, "nan")], HEAD, "not finite"),
    ],
)
def test_parse_rejects_bad_files(rows, header, message):
    with pytest.raises(DatasetError, match=message):
        parse(rows, header=header)


def test_parse_rejects_no_header_and_one_row():
    with pytest.raises(DatasetError, match="no header"):
        parse_measurement_csv("")
    with pytest.raises(DatasetError, match="at least two rows"):
        parse([("2025-01-15T10:00:00", 100.0, 20.0, 20.0, 1.0)])


# analysis tests


def test_analysis_runs_the_rows_through_the_twin():
    dataset, rows = night_and_day_dataset()

    report = analyse_dataset(dataset, CONFIG)

    assert report.name == "day"
    assert len(report.samples) == len(rows)
    for sample, row in zip(report.samples, rows):
        stamp, g, t, v, i = row
        assert sample.timestamp == np.datetime64(stamp, "s")
        assert sample.true_irradiance == pytest.approx(g)  # a dataset has no hidden truth
        assert sample.true_temperature == pytest.approx(t)
        assert sample.measured_irradiance == pytest.approx(g)
        assert sample.measured_voltage == pytest.approx(v)
        assert sample.active_faults == ()
        curve = solve_curve(CONFIG.datasheet, g, t)
        expected = power_at_voltage(curve, v) if v > 0 else curve.mpp_power  # at the measured voltage
        assert sample.power_predicted == pytest.approx(expected)
        assert sample.power_measured == pytest.approx(v * i)


def test_analysis_states_follow_the_run_rules_at_the_config_thresholds():
    dataset, _rows = night_and_day_dataset()

    report = analyse_dataset(dataset, replace(CONFIG, thresholds=Thresholds(warning_pct=1.0, abnormal_pct=5.0)))
    samples = report.samples

    night = samples[0]
    assert night.deviation_pct == 0.0  # below the power floor the deviation is 0 and the State Normal
    assert night.state is State.NORMAL
    # A hot bright midday reading: the twin under-predicts a warmed module, so the deviation
    # is positive, above 5 % at these thresholds.
    assert samples[2].deviation_pct > 5.0
    assert samples[2].state is State.ABNORMAL


def test_analysis_metrics_match_plain_math_and_the_validation_rules():
    dataset, rows = night_and_day_dataset()

    report = analyse_dataset(dataset, CONFIG)
    samples = report.samples
    daylight = [sample for sample in samples if sample.power_predicted >= POWER_FLOOR_W]
    actual = np.array([sample.power_measured for sample in daylight])
    estimated = np.array([sample.power_predicted for sample in daylight])

    metrics = report.metrics
    reference = error_metrics(samples)
    assert metrics.mae_w == reference.mae_w
    assert metrics.rmse_w == reference.rmse_w
    assert metrics.mape_pct == reference.mape_pct
    assert metrics.sample_count == reference.sample_count
    assert metrics.row_count == len(rows)
    assert metrics.mean_actual_w == pytest.approx(float(np.mean(actual)), rel=1e-9)
    assert metrics.mean_estimated_w == pytest.approx(float(np.mean(estimated)), rel=1e-9)
    assert metrics.mbe_w == pytest.approx(float(np.mean(estimated - actual)), rel=1e-9)
    counts = {state: sum(sample.state is state for sample in daylight) for state in State}
    assert metrics.normal_pct == pytest.approx(counts[State.NORMAL] / len(daylight) * 100.0)
    assert metrics.warning_pct == pytest.approx(counts[State.WARNING] / len(daylight) * 100.0)
    assert metrics.abnormal_pct == pytest.approx(counts[State.ABNORMAL] / len(daylight) * 100.0)


def test_a_run_exported_as_measurements_scores_the_same_as_the_live_run():
    """The twin sees the same measured G and T, so the dataset score must equal the run's."""
    result = run(replace(CONFIG, time_step_s=600.0))
    rows = [
        (
            np.datetime_as_string(sample.timestamp, unit="s"),
            sample.measured_irradiance,
            sample.measured_temperature,
            sample.measured_voltage,
            sample.measured_current,
            sample.power_measured,
        )
        for sample in result.samples
    ]
    dataset = parse(rows, header=HEAD_WITH_POWER)

    report = analyse_dataset(dataset, CONFIG)
    reference = error_metrics(result)

    # The run compares the plant's maximum power with the twin's; the dataset predicts at the voltage the
    # plant sat at, which is a hair below the twin's maximum, so the two agree closely but not exactly.
    for scored, live in zip(report.samples, result.samples):
        assert scored.power_predicted == pytest.approx(live.power_predicted, rel=0.01)
        assert scored.power_predicted <= live.power_predicted * (1 + 1e-4)
        assert scored.deviation_pct == pytest.approx(live.deviation_pct, abs=1.0)
        assert scored.state is live.state
    assert report.metrics.mae_w == pytest.approx(reference.mae_w, abs=0.5)
    assert report.metrics.rmse_w == pytest.approx(reference.rmse_w, abs=0.5)


def test_analysis_of_a_dataset_without_daylight_is_rejected():
    dataset = parse(
        [
            ("2025-01-15T00:30:00", 0.0, 18.0, 0.0, 0.0),
            ("2025-01-15T01:30:00", 0.0, 17.5, 0.0, 0.0),
        ]
    )

    with pytest.raises(ValueError, match="no daylight"):
        analyse_dataset(dataset, CONFIG)


# store tests


def test_the_store_round_trips_a_dataset(tmp_path):
    store = DatasetStore(tmp_path)
    dataset, _rows = night_and_day_dataset()

    name = store.save("My Test 2026", dataset)
    back = store.read(name)

    assert name == "My Test 2026"
    assert back.name == "My Test 2026"
    assert np.array_equal(back.timestamps, dataset.timestamps)
    for column in ("irradiance", "temperature", "voltage", "current", "power"):
        assert np.allclose(getattr(back, column), getattr(dataset, column))
    assert store.names() == ["My Test 2026"]


def test_the_store_replaces_a_dataset_of_the_same_name(tmp_path):
    store = DatasetStore(tmp_path)
    first, _rows = night_and_day_dataset()
    second = Measurements(
        name="n",
        timestamps=first.timestamps[:2],
        irradiance=first.irradiance[:2],
        temperature=first.temperature[:2],
        voltage=first.voltage[:2],
        current=first.current[:2],
        power=first.power[:2],
    )

    store.save("demo", first)
    store.save("demo", second)

    assert store.names() == ["demo"]
    assert len(store.read("demo").timestamps) == 2


def test_the_store_rejects_a_path_like_name_and_a_missing_delete(tmp_path):
    store = DatasetStore(tmp_path)

    with pytest.raises(DatasetError, match="not a dataset name"):
        store.save("../escape", night_and_day_dataset()[0])
    store.save("demo", night_and_day_dataset()[0])
    store.delete("demo")
    with pytest.raises(DatasetError, match="no dataset"):
        store.delete("demo")
    with pytest.raises(DatasetError, match="could not read"):
        store.read("demo")


def test_default_datasets_dir_follows_the_environment(monkeypatch, tmp_path):
    monkeypatch.delenv(DATASETS_DIR_ENV, raising=False)
    monkeypatch.setattr("pvysics.dataset.Path.home", lambda: tmp_path / "home")

    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    assert default_datasets_dir() == tmp_path / "xdg" / "pvysics" / "datasets"

    monkeypatch.setenv(DATASETS_DIR_ENV, str(tmp_path / "chosen"))
    assert default_datasets_dir() == tmp_path / "chosen"

    monkeypatch.delenv(DATASETS_DIR_ENV)
    monkeypatch.delenv("XDG_DATA_HOME")
    assert default_datasets_dir() == tmp_path / "home" / ".local" / "share" / "pvysics" / "datasets"


def test_default_store_uses_the_default_dir(monkeypatch, tmp_path):
    monkeypatch.setenv(DATASETS_DIR_ENV, str(tmp_path / "chosen"))

    assert isinstance(default_store(), DatasetStore)
    assert (tmp_path / "chosen").is_dir()


# ---- the upload template and Excel files ------------------------------------------------------------------------

import zipfile  # noqa: E402

from pvysics.dataset import (  # noqa: E402
    TEMPLATE_HEADER,
    TEMPLATE_ROWS,
    analyse_dataset,
    read_measurement_file,
    write_template,
)
from pvysics.run import bundled_run_config  # noqa: E402


def excel_book(path, rows, shared=None):
    """A workbook as Excel writes it: text through a shared-strings table, numbers and dates as plain numbers."""
    main = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    shared = shared or []
    cells = []
    for number, row in enumerate(rows, start=1):
        items = []
        for column, value in enumerate(row):
            ref = f"{'ABCDEFGH'[column]}{number}"
            if isinstance(value, str):
                items.append(f'<c r="{ref}" t="s"><v>{shared.index(value)}</v></c>')
            else:
                items.append(f'<c r="{ref}" s="1"><v>{value}</v></c>')
        cells.append(f'<row r="{number}">{"".join(items)}</row>')
    with zipfile.ZipFile(path, "w") as book:
        book.writestr("xl/workbook.xml", f'<workbook xmlns="{main}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Data" sheetId="1" r:id="rId7"/></sheets></workbook>')
        book.writestr("xl/_rels/workbook.xml.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId7" Type="x" Target="worksheets/data.xml"/></Relationships>')
        book.writestr("xl/sharedStrings.xml", f'<sst xmlns="{main}">' + "".join(f"<si><t>{s}</t></si>" for s in shared) + "</sst>")
        book.writestr("xl/worksheets/data.xml", f'<worksheet xmlns="{main}"><sheetData>{"".join(cells)}</sheetData></worksheet>')


@pytest.mark.parametrize("suffix", [".csv", ".xlsx"])
def test_the_template_reads_back_as_a_valid_dataset(tmp_path, suffix):
    path = tmp_path / f"template{suffix}"

    write_template(path)
    dataset = read_measurement_file(path)

    assert len(dataset.timestamps) == len(TEMPLATE_ROWS)
    assert dataset.irradiance[0] == TEMPLATE_ROWS[0][1]
    assert dataset.power[0] == pytest.approx(TEMPLATE_ROWS[0][3] * TEMPLATE_ROWS[0][4])
    report = analyse_dataset(dataset, bundled_run_config(seed=1))
    assert report.metrics.row_count == len(TEMPLATE_ROWS)


def test_the_template_rows_are_a_healthy_module_and_score_normal(tmp_path):
    write_template(tmp_path / "t.csv")
    dataset = read_measurement_file(tmp_path / "t.csv")
    config = bundled_run_config(seed=1)

    report = analyse_dataset(dataset, config)

    for _, g, t, v, i in TEMPLATE_ROWS:
        curve = solve_curve(config.datasheet, g, t)
        assert i <= curve.mpp_current * 1.01
        assert v * i <= curve.mpp_power
    assert report.metrics.normal_pct == 100.0
    assert all(sample.state is State.NORMAL for sample in report.samples)


def test_a_healthy_module_held_off_its_maximum_power_point_scores_normal():
    """A load that holds the module at 24 V: it makes less than its maximum, but exactly what the SDM says."""
    curve = solve_curve(CONFIG.datasheet, 800.0, 35.0)
    voltage = 24.0
    current = float(np.interp(voltage, curve.voltage, curve.current))
    rows = [("2025-01-15T10:00:00", 800.0, 35.0, voltage, current), ("2025-01-15T10:01:00", 800.0, 35.0, voltage, current)]

    report = analyse_dataset(parse(rows), CONFIG)

    assert curve.mpp_power - voltage * current > 10.0  # clearly off the maximum power point
    assert all(sample.state is State.NORMAL for sample in report.samples)
    assert report.metrics.mean_deviation_pct == pytest.approx(0.0, abs=0.01)
    assert report.mpp_power_w == pytest.approx((curve.mpp_power, curve.mpp_power))  # the reference is kept


def test_a_file_with_only_power_is_predicted_at_the_maximum_power_point():
    curve = solve_curve(CONFIG.datasheet, 800.0, 35.0)
    header = ("timestamp", "irradiance_w_m2", "temperature_c", "power_w")
    rows = [("2025-01-15T10:00:00", 800.0, 35.0, 150.0), ("2025-01-15T10:01:00", 800.0, 35.0, 150.0)]

    report = analyse_dataset(parse(rows, header=header), CONFIG)

    assert report.samples[0].power_predicted == pytest.approx(curve.mpp_power)


def test_a_fault_still_shows_when_the_voltage_is_known():
    """Shading cuts the current at the same voltage: the twin's current there is higher, so it deviates."""
    curve = solve_curve(CONFIG.datasheet, 800.0, 35.0)
    voltage = float(curve.mpp_voltage)
    current = float(np.interp(voltage, curve.voltage, curve.current)) * 0.7
    rows = [("2025-01-15T10:00:00", 800.0, 35.0, voltage, current), ("2025-01-15T10:01:00", 800.0, 35.0, voltage, current)]

    report = analyse_dataset(parse(rows), CONFIG)

    assert all(sample.state is State.ABNORMAL for sample in report.samples)
    assert report.samples[0].deviation_pct == pytest.approx(-30.0, abs=0.5)


def test_power_at_voltage_is_zero_outside_the_curve():
    curve = solve_curve(CONFIG.datasheet, 800.0, 35.0)

    assert power_at_voltage(curve, 0.0) == 0.0
    assert power_at_voltage(curve, float(curve.voltage[-1]) + 1.0) == 0.0
    assert power_at_voltage(curve, float(curve.mpp_voltage)) == pytest.approx(curve.mpp_power, rel=1e-3)


def test_the_csv_template_has_the_documented_columns(tmp_path):
    write_template(tmp_path / "t.csv")

    header = (tmp_path / "t.csv").read_text(encoding="utf-8").splitlines()[0]

    assert header.split(",") == list(TEMPLATE_HEADER)


def test_the_excel_template_has_an_instructions_sheet(tmp_path):
    write_template(tmp_path / "t.xlsx")

    with zipfile.ZipFile(tmp_path / "t.xlsx") as book:
        assert "xl/worksheets/sheet2.xml" in book.namelist()
        assert b"Instructions" in book.read("xl/workbook.xml")


def test_an_excel_file_with_shared_strings_and_date_serials_is_read(tmp_path):
    shared = ["Timestamp", "G", "Temp", "PV Voltage", "PV Current"]
    # 45672.4166667 is 2025-01-15 10:00, and a minute later; Excel saves a date as such a number
    rows = [shared, [45672.4166667, 812.5, 35.2, 29.6, 7.9], [45672.4173611, 820.1, 35.4, 29.6, 8.1]]
    path = tmp_path / "log.xlsx"
    excel_book(path, rows, shared)

    dataset = read_measurement_file(path)

    assert str(dataset.timestamps[0]) == "2025-01-15T10:00:00"
    assert str(dataset.timestamps[1]) == "2025-01-15T10:01:00"
    assert dataset.irradiance.tolist() == [812.5, 820.1]
    assert dataset.name == "log"


def test_an_excel_file_with_a_missing_column_says_what_is_missing(tmp_path):
    shared = ["Timestamp", "G"]
    path = tmp_path / "short.xlsx"
    excel_book(path, [shared, [45672.5, 800.0], [45672.6, 810.0]], shared)

    with pytest.raises(DatasetError, match="temperature"):
        read_measurement_file(path)


def test_a_csv_with_a_byte_order_mark_from_excel_is_read(tmp_path):
    path = tmp_path / "excel.csv"
    path.write_bytes(b"\xef\xbb\xbf" + b"timestamp,irradiance_w_m2,temperature_c,power_w\n2025-01-15T10:00:00,800,30,150\n2025-01-15T10:01:00,805,30,152\n")

    assert len(read_measurement_file(path).timestamps) == 2


@pytest.mark.parametrize("name", ["data.txt", "data.xls", "data"])
def test_other_file_types_are_refused_with_a_plain_message(tmp_path, name):
    path = tmp_path / name
    path.write_text("x", encoding="utf-8")

    with pytest.raises(DatasetError, match="not a .csv or .xlsx"):
        read_measurement_file(path)


def test_a_file_that_is_not_a_workbook_is_refused(tmp_path):
    path = tmp_path / "fake.xlsx"
    path.write_text("not a zip", encoding="utf-8")

    with pytest.raises(DatasetError, match="could not read"):
        read_measurement_file(path)


def test_the_template_only_comes_as_csv_or_xlsx(tmp_path):
    with pytest.raises(DatasetError):
        write_template(tmp_path / "t.pdf")
