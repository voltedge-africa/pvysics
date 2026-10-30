"""Datasets: measurements imported as CSV, scored by the twin. Headless, no Qt.

A dataset is a table of the plant's readings such as an ESP32 would log: a timestamp per
row, the irradiance and temperature the twin sees, and the electrical power (a power column,
or a voltage and current pair whose product is the actual power). analyse_dataset() runs the
rows through the twin exactly the way a run does: the twin predicts power from the rows'
irradiance and temperature, and the power deviation and State follow from the run's rules
(run.py). The rows' true inputs are the measured ones, because a dataset has no hidden truth.
So real measurements go through the same estimator the simulated plant does, and the app
works without an ESP32.

The DatasetStore keeps imported datasets as CSV files in one directory, one file per dataset,
so a dataset lives between runs of the app and appears in the Dataset list.
"""

import csv
import io
import math
import os
import zipfile
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from pvysics.profile import (
    ProfileError,
    IRRADIANCE_NAMES,
    MISSING_VALUE,
    TEMPERATURE_NAMES,
    TIMESTAMP_NAMES,
    csv_columns,
)
from pvysics.run import POWER_FLOOR_W, RunConfig, Sample, State, Thresholds
from pvysics.single_diode import power_at_voltage, solve_curve
from pvysics.spreadsheet import (
    CSV_SUFFIX,
    XLSX_SUFFIX,
    SpreadsheetError,
    write_table,
    xlsx_to_csv_text,
)
from pvysics.validation import NEAR_ZERO_W, ErrorMetrics, error_metrics

DATASETS_DIR_ENV = "PVYSICS_DATASETS_DIR"
POWER_FLOOR_EXCLUDED_NOTE = "night rows (estimated power below the 5 W floor) never dilute them"

TIMESTAMP_COLUMNS = (*TIMESTAMP_NAMES,)
IRRADIANCE_COLUMNS = (*IRRADIANCE_NAMES, "irradiance_w_m2", "ghi_w_m2")
TEMPERATURE_COLUMNS = (*TEMPERATURE_NAMES, "temperature_c", "module_temperature", "temp", "pv_temp")
VOLTAGE_COLUMNS = ("pv_voltage", "voltage", "module_voltage", "voltage_v", "v")
CURRENT_COLUMNS = ("pv_current", "current", "module_current", "current_a", "i")
POWER_COLUMNS = ("actual_power", "actual_power_w", "power", "power_w", "pv_power", "p")
STORE_COLUMNS = (
    "timestamp",
    "irradiance_w_m2",
    "temperature_c",
    "voltage_v",
    "current_a",
    "power_w",
)


# The template a user fills in: the canonical column names (all recognised by the importer), a few example
# rows from a clear morning, and a plain-language note on each column for the Excel version's second sheet.
# The example rows are a healthy generic 250 W module, a hair under the twin's maximum power at each row's
# irradiance and temperature (a test checks this), so the template scores Normal until the user fills in their own.
TEMPLATE_HEADER = ("timestamp", "irradiance_w_m2", "temperature_c", "voltage_v", "current_a")
TEMPLATE_ROWS = (
    ("2025-01-15T09:00:00", 612.4, 31.8, 29.0, 5.10),
    ("2025-01-15T09:01:00", 618.9, 31.9, 29.0, 5.15),
    ("2025-01-15T09:02:00", 625.3, 32.0, 29.0, 5.20),
    ("2025-01-15T09:03:00", 631.7, 32.2, 29.0, 5.25),
    ("2025-01-15T09:04:00", 638.0, 32.3, 29.0, 5.30),
)
TEMPLATE_NOTES = (
    ("Column", "What to put in it"),
    ("timestamp", "Date and time of the reading, for example 2025-01-15T09:00:00. Times must increase; the step may vary."),
    ("irradiance_w_m2", "Irradiance in W/m2 on the module, from your irradiance sensor. Not negative."),
    ("temperature_c", "Module temperature in degrees C."),
    ("voltage_v", "Module voltage in V."),
    ("current_a", "Module current in A. The actual power is voltage times current."),
    ("Power instead", "Or replace voltage_v and current_a by one column named power_w holding the actual power in W."),
    ("Delete the examples", "Delete the example rows on the Measurements sheet, then paste your own readings from row 2."),
)


class DatasetError(ValueError):
    """The dataset CSV is missing columns, is too short, or has invalid values."""


@dataclass(frozen=True)
class Measurements:
    """The rows of an imported dataset, one per row of the CSV, in time order.

    power is the actual power when the file named a power column, otherwise the product
    of voltage and current.
    """

    name: str
    timestamps: NDArray[np.datetime64]
    irradiance: NDArray[np.float64]  # W/m^2, seen by the twin
    temperature: NDArray[np.float64]  # degrees C, seen by the twin
    voltage: NDArray[np.float64]  # V
    current: NDArray[np.float64]  # A
    power: NDArray[np.float64]  # W, the actual power


@dataclass(frozen=True)
class DatasetColumns:
    """The header column that holds each role. An empty power name means the file had none."""

    timestamp: str
    irradiance: str
    temperature: str
    voltage: str
    current: str
    power: str


@dataclass(frozen=True)
class DatasetMetrics:
    """The accuracy of the twin on a dataset, over daylight rows (POWER_FLOOR_EXCLUDED_NOTE applies).

    mbe is the mean of estimated minus actual power, in W: positive means the twin over-predicts.
    mean_deviation_pct is the mean of the signed power deviation in percent, so the same sign
    convention holds. The state shares are percents of the daylight rows in each State.
    """

    mae_w: float
    rmse_w: float
    mape_pct: float
    sample_count: int  # daylight rows used for MAE and RMSE
    mape_sample_count: int  # daylight rows with actual power at or above NEAR_ZERO_W
    row_count: int  # every row of the dataset
    mean_irradiance_w_m2: float
    mean_actual_w: float
    mean_estimated_w: float
    mbe_w: float
    mean_deviation_pct: float
    normal_pct: float
    warning_pct: float
    abnormal_pct: float


@dataclass(frozen=True)
class DatasetReport:
    """One dataset analysed by the twin: every row as a Sample, and the metrics."""

    name: str
    config: RunConfig  # the datasheet and thresholds the rows were scored with
    samples: list[Sample]
    metrics: DatasetMetrics
    # The module's maximum power at each row's irradiance and temperature, a reference next to the estimate.
    mpp_power_w: tuple[float, ...] = ()


def parse_measurement_csv(text: str, name: str = "") -> Measurements:
    """Build the Measurements of CSV text of the plant's readings.

    The header must name a timestamp, irradiance and temperature column, and the actual power
    either through a power column or a voltage and current pair. Times must increase (any
    step is allowed, as real logs have gaps), each value must be a finite number and not the
    missing-value marker -999, and irradiance must not be negative. The voltage and current
    may read slightly negative at night (sensor noise; the product is used as it is).
    """
    try:
        header = csv_columns(text)
    except ProfileError as error:  # an empty file or a broken header line
        raise DatasetError(str(error)) from error
    columns = _columns(header)
    return _measurements(text, columns, name)


def read_measurement_file(path: Path) -> Measurements:
    """The Measurements of a .csv or .xlsx file, named after the file. Anything else is an error."""
    path = Path(path)
    suffix = path.suffix.lower()
    try:
        if suffix == CSV_SUFFIX:
            text = path.read_text(encoding="utf-8-sig")  # Excel's "CSV UTF-8" starts with a byte order mark
        elif suffix == XLSX_SUFFIX:
            text = xlsx_to_csv_text(path, TIMESTAMP_COLUMNS)
        else:
            raise DatasetError(f"{path.name} is not a .csv or .xlsx file")
    except (OSError, UnicodeError, zipfile.BadZipFile, SpreadsheetError) as error:
        raise DatasetError(f"could not read {path.name}: {error}") from error
    return parse_measurement_csv(text, name=path.stem)


def write_template(path: Path) -> None:
    """Write the upload template as .csv or .xlsx, by the path's suffix. The workbook also has an Instructions sheet."""
    try:
        write_table(path, TEMPLATE_HEADER, TEMPLATE_ROWS, TEMPLATE_NOTES, sheet="Measurements")
    except SpreadsheetError as error:
        raise DatasetError(f"the template is a .csv or .xlsx file, not '{Path(path).suffix}'") from error


def analyse_dataset(dataset: Measurements, config: RunConfig) -> DatasetReport:
    """The twin's prediction, deviation and State per row, plus the metrics of the whole dataset.

    The twin predicts power from the rows' irradiance and temperature with the config's
    datasheet, at the nominal parameters. A row with a measured voltage is predicted at that
    voltage (V times the twin's current there), so a module held off its maximum power point by
    its load is not mistaken for a fault. A row with no voltage, such as a file that has only
    power, is predicted at the maximum power point, which assumes the module is tracked there.
    The State follows the config's thresholds. The maximum power is kept per row as a reference.
    """
    samples, mpp_power = _sample_rows(dataset, config)
    return DatasetReport(
        name=dataset.name,
        config=config,
        samples=samples,
        metrics=_metrics(samples),
        mpp_power_w=tuple(mpp_power),
    )


class DatasetStore:
    """The datasets the user imported, as CSV files in one directory.

    Files are named after the dataset and hold the canonical columns (STORE_COLUMNS), so a
    stored dataset reads back the same way whatever the original file's spellings were.
    """

    def __init__(self, directory: Path) -> None:
        self._directory = Path(directory)
        self._directory.mkdir(parents=True, exist_ok=True)

    def names(self) -> list[str]:
        """The dataset names, in file-name order."""
        return sorted(path.stem for path in self._directory.glob("*.csv"))

    def save(self, name: str, dataset: Measurements) -> str:
        """Store a dataset under name, replacing any dataset of the same name. Returns the name."""
        name = _store_name(name)
        rows: list[list[str | float]] = []
        for timestamp, irradiance, temperature, voltage, current, power in zip(
            dataset.timestamps,
            dataset.irradiance,
            dataset.temperature,
            dataset.voltage,
            dataset.current,
            dataset.power,
        ):
            rows.append(
                [
                    np.datetime_as_string(timestamp, unit="s"),
                    float(irradiance),
                    float(temperature),
                    float(voltage),
                    float(current),
                    float(power),
                ]
            )
        with self._path(name).open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(("timestamp", "irradiance_w_m2", "temperature_c", "voltage_v", "current_a", "power_w"))
            writer.writerows(rows)
        return name

    def read(self, name: str) -> Measurements:
        """Read a stored dataset back."""
        return parse_measurement_csv(self._text(name), name=name)

    def delete(self, name: str) -> None:
        """Remove a stored dataset. A missing name is an error."""
        path = self._path(_store_name(name))
        if not path.exists():
            raise DatasetError(f"there is no dataset '{name}' in {self._directory}")
        path.unlink()

    def _path(self, name: str) -> Path:
        return self._directory / f"{_store_name(name)}.csv"

    def _text(self, name: str) -> str:
        path = self._path(name)
        try:
            return path.read_text(encoding="utf-8")
        except OSError as error:
            raise DatasetError(f"could not read dataset '{name}': {error}") from error


def default_datasets_dir() -> Path:
    """Where imported datasets live: $PVYSICS_DATASETS_DIR, else the platform's data folder."""
    override = os.environ.get(DATASETS_DIR_ENV)
    if override:
        return Path(override)
    if os.name == "nt":
        base = os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming"
    elif os.uname().sysname == "Darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share"
    return Path(base) / "pvysics" / "datasets"


def default_store() -> DatasetStore:
    """The store the app keeps datasets in."""
    return DatasetStore(default_datasets_dir())


def _columns(header: list[str]) -> DatasetColumns:
    """Match the header's names to the roles. Unmatched voltage and current are allowed to fall
    away when a power column is there; unmatched timestamp, irradiance or temperature are not."""
    def _key(column: str) -> str:
        """Case and separators away: 'PV Voltage' reads as 'pv_voltage'."""
        return "_".join(column.lower().replace("-", " ").split())

    lowered = {_key(column): column for column in header}
    columns = DatasetColumns(
        timestamp=_match(lowered, TIMESTAMP_COLUMNS),
        irradiance=_match(lowered, IRRADIANCE_COLUMNS),
        temperature=_match(lowered, TEMPERATURE_COLUMNS),
        voltage=_match(lowered, VOLTAGE_COLUMNS),
        current=_match(lowered, CURRENT_COLUMNS),
        power=_match(lowered, POWER_COLUMNS),
    )
    missing = [
        role
        for role, column in (
            ("timestamp", columns.timestamp),
            ("irradiance", columns.irradiance),
            ("temperature", columns.temperature),
        )
        if not column
    ]
    if missing:
        raise DatasetError(
            f"no column matches {', '.join(missing)}; the file has: {', '.join(header)}"
        )
    if not columns.power and not (columns.voltage and columns.current):
        raise DatasetError(
            "the actual power needs either a power column or a voltage and current pair; "
            f"the file has: {', '.join(header)}"
        )
    if columns.voltage == columns.temperature or columns.current == columns.temperature:
        raise DatasetError("the same column cannot hold the temperature and the electrical readings")
    return columns


def _match(lowered: dict[str, str], names: tuple[str, ...]) -> str:
    for name in names:
        if name.lower() in lowered:
            return lowered[name.lower()]
    return ""


def _measurements(text: str, columns: DatasetColumns, name: str) -> Measurements:
    """Read the mapped columns row by row. The checks are the profile's, minus the step rule."""
    stamps: list[np.datetime64] = []
    irradiance: list[float] = []
    temperature: list[float] = []
    voltage: list[float] = []
    current: list[float] = []
    power: list[float] = []
    for number, row in enumerate(csv.DictReader(io.StringIO(text)), start=1):
        where = f"row {number}"
        stamp = _stamp(row, columns.timestamp, where)
        g = _number(row.get(columns.irradiance), "irradiance", where)
        if g < 0.0:
            raise DatasetError(f"{where}: irradiance is negative")
        t = _number(row.get(columns.temperature), "temperature", where)
        v = 0.0 if not columns.voltage else _number(row.get(columns.voltage), "voltage", where)
        i = 0.0 if not columns.current else _number(row.get(columns.current), "current", where)
        p = _number(row.get(columns.power), "power", where) if columns.power else v * i
        stamps.append(stamp)
        irradiance.append(g)
        temperature.append(t)
        voltage.append(v)
        current.append(i)
        power.append(p)
    if len(stamps) < 2:
        raise DatasetError("the dataset needs at least two rows")
    for earlier, later in zip(stamps, stamps[1:]):
        if later <= earlier:
            raise DatasetError(f"{_label(later)}: time does not increase after the row before")
    return Measurements(
        name=name,
        timestamps=np.array(stamps, dtype="datetime64[s]"),
        irradiance=np.array(irradiance, dtype=np.float64),
        temperature=np.array(temperature, dtype=np.float64),
        voltage=np.array(voltage, dtype=np.float64),
        current=np.array(current, dtype=np.float64),
        power=np.array(power, dtype=np.float64),
    )


def _sample_rows(dataset: Measurements, config: RunConfig) -> tuple[list[Sample], list[float]]:
    """Each row as a Sample through the twin, and the twin's maximum power for each row.

    The true inputs equal the measured ones (no hidden truth in a dataset) and no faults are
    active, because a dataset carries none. The deviation is zero below POWER_FLOOR_W of
    predicted power, the rule a run's step uses.
    """
    samples: list[Sample] = []
    mpp_power: list[float] = []
    for index, stamp in enumerate(dataset.timestamps):
        g, t = float(dataset.irradiance[index]), float(dataset.temperature[index])
        voltage = float(dataset.voltage[index])
        curve = solve_curve(config.datasheet, g, t)
        power_predicted = power_at_voltage(curve, voltage) if voltage > 0.0 else curve.mpp_power
        mpp_power.append(curve.mpp_power)
        power_measured = float(dataset.power[index])
        deviation = 0.0
        if power_predicted >= POWER_FLOOR_W:
            deviation = (power_measured - power_predicted) / power_predicted * 100.0
        samples.append(
            Sample(
                timestamp=stamp,
                true_irradiance=g,
                true_temperature=t,
                measured_irradiance=g,
                measured_temperature=t,
                measured_voltage=voltage,
                measured_current=float(dataset.current[index]),
                power_measured=power_measured,
                power_predicted=power_predicted,
                deviation_pct=deviation,
                state=_state(deviation, config.thresholds),
            )
        )
    return samples, mpp_power


def _metrics(samples: list[Sample]) -> DatasetMetrics:
    """The dataset's metrics. Accuracy is over the daylight rows; the shares are shares of them."""
    errors = error_metrics(samples)
    daylight = [sample for sample in samples if sample.power_predicted >= POWER_FLOOR_W]
    actual = np.array([sample.power_measured for sample in daylight])
    estimated = np.array([sample.power_predicted for sample in daylight])
    return DatasetMetrics(
        **asdict(errors),
        row_count=len(samples),
        mean_irradiance_w_m2=float(np.mean([sample.measured_irradiance for sample in daylight])),
        mean_actual_w=float(np.mean(actual)),
        mean_estimated_w=float(np.mean(estimated)),
        mbe_w=float(np.mean(estimated - actual)),
        mean_deviation_pct=float(np.mean([sample.deviation_pct for sample in daylight])),
        normal_pct=_share(daylight, State.NORMAL),
        warning_pct=_share(daylight, State.WARNING),
        abnormal_pct=_share(daylight, State.ABNORMAL),
    )


def _share(daylight: list[Sample], state: State) -> float:
    return sum(sample.state is state for sample in daylight) / len(daylight) * 100.0


def _state(deviation_pct: float, thresholds: Thresholds) -> State:
    """The run's State rule: over the abnormal limit, over the warning limit, else Normal."""
    magnitude = abs(deviation_pct)
    if magnitude > thresholds.abnormal_pct:
        return State.ABNORMAL
    if magnitude > thresholds.warning_pct:
        return State.WARNING
    return State.NORMAL


def _store_name(name: str) -> str:
    """A dataset name is one file name: short, and never a path."""
    name = name.strip()
    if not name or name in (".", "..") or "/" in name or "\\" in name or "\x00" in name:
        raise DatasetError(f"'{name}' is not a dataset name")
    return name


def _stamp(row: dict, column: str, where: str) -> np.datetime64:
    text = (row.get(column) or "").strip()
    try:
        stamp = datetime.fromisoformat(text)
    except ValueError as error:
        raise DatasetError(f"{where}: timestamp '{text}' is not an ISO date and time") from error
    return np.datetime64(stamp.replace(tzinfo=None), "s")


def _number(text: str | None, role: str, where: str) -> float:
    if text is None or not text.strip():
        raise DatasetError(f"{where}: {role} is missing")
    try:
        value = float(text)
    except ValueError as error:
        raise DatasetError(f"{where}: {role} '{text}' is not a number") from error
    if value == MISSING_VALUE:
        raise DatasetError(f"{where}: {role} is the missing-value marker -999")
    if not math.isfinite(value):
        raise DatasetError(f"{where}: {role} is not finite")
    return value


def _label(stamp: np.datetime64) -> str:
    return str(stamp.astype("datetime64[s]"))

