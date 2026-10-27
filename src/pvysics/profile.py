"""Profile loader: the irradiance and temperature series that drive a run.

Two sources share one set of checks. parse_profile_csv reads one bundled NASA POWER day.
parse_profile_table reads any CSV through a ColumnMap, such as a file the user loads.
Both reject missing values, non-finite values, negative irradiance, time that does not
increase and gaps. A Profile is never filled in or repaired.
"""

import csv
import io
import math
import zipfile
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from importlib.resources import files
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from pvysics.spreadsheet import CSV_SUFFIX, XLSX_SUFFIX, SpreadsheetError, write_table, xlsx_to_csv_text

BUNDLED_CSV = "durban_power_hourly.csv"
BUNDLED_DAYS = (date(2025, 1, 15), date(2025, 1, 16), date(2025, 1, 17))
MISSING_VALUE = -999.0
NASA_TIMESTAMP = "YEAR,MO,DY,HR"  # stands for the four NASA POWER columns, not one column
NASA_COLUMNS = ("YEAR", "MO", "DY", "HR")
TIMESTAMP_NAMES = ("timestamp", "time", "datetime", "date")
IRRADIANCE_NAMES = ("G", "ghi", "irradiance", "ALLSKY_SFC_SW_DWN")
TEMPERATURE_NAMES = ("T", "temp_air", "temperature", "T2M")


# The weather template: a clear day, hourly, with the column names the loader finds by itself. Irradiance in W/m2,
# temperature in degrees C. The values are a smooth example (a half sine of irradiance), to be replaced.
PROFILE_TEMPLATE_HEADER = ("timestamp", "irradiance", "temperature")
PROFILE_TEMPLATE_ROWS = tuple(
    (
        f"2025-01-15T{hour:02d}:00:00",
        round(max(0.0, 900.0 * math.sin(math.pi * (hour - 6) / 12.0)), 1),
        round(18.0 + 10.0 * math.sin(math.pi * (hour - 9) / 12.0), 1),
    )
    for hour in range(24)
)
PROFILE_TEMPLATE_NOTES = (
    ("Column", "What to put in it"),
    ("timestamp", "Date and time of each value, for example 2025-01-15T09:00:00. Times must step by one fixed amount, with no gaps."),
    ("irradiance", "Irradiance in W/m2 on the module (global horizontal or in-plane). Not negative."),
    ("temperature", "Air temperature in degrees C."),
    ("Rules", "Every cell must hold a number (no blanks, no -999). The file has one row per time step."),
    ("Delete the examples", "Delete the 24 example rows on the Profile sheet, then paste your own from row 2."),
)


class ProfileError(ValueError):
    """The profile data is missing, has gaps, or has invalid values."""


def read_profile_text(path: Path) -> str:
    """The text of a profile file as CSV: a .csv as it is, an .xlsx as the CSV of its first sheet."""
    path = Path(path)
    suffix = path.suffix.lower()
    try:
        if suffix == CSV_SUFFIX:
            return path.read_text(encoding="utf-8-sig")
        if suffix == XLSX_SUFFIX:
            return xlsx_to_csv_text(path, TIMESTAMP_NAMES)
    except (OSError, UnicodeError, zipfile.BadZipFile, SpreadsheetError) as error:
        raise ProfileError(f"cannot read {path.name} ({error})") from error
    raise ProfileError(f"{path.name} is not a .csv or .xlsx file")


def write_profile_template(path: Path) -> None:
    """Write the weather template as .csv or .xlsx, by the path's suffix. The workbook also has an Instructions sheet."""
    try:
        write_table(path, PROFILE_TEMPLATE_HEADER, PROFILE_TEMPLATE_ROWS, PROFILE_TEMPLATE_NOTES, sheet="Profile")
    except SpreadsheetError as error:
        raise ProfileError(f"the template is a .csv or .xlsx file, not '{Path(path).suffix}'") from error


@dataclass(frozen=True)
class Profile:
    """A series of G in W/m^2 (mean over each step) and T in degrees C, with the file or day it came from."""

    timestamps: NDArray[np.datetime64]
    irradiance: NDArray[np.float64]
    temperature: NDArray[np.float64]
    name: str = ""


@dataclass(frozen=True)
class ColumnMap:
    """The header column that holds each input. An empty name means no column was chosen."""

    timestamp: str  # a header name, or NASA_TIMESTAMP for the YEAR, MO, DY, HR columns
    irradiance: str
    temperature: str


def parse_profile_csv(text: str, day: date) -> Profile:
    """Build the Profile for `day` from NASA POWER style CSV text.

    The day needs 24 hourly rows, 00:00 to 23:00, in order with no gaps.
    """
    stamps: list[datetime] = []
    irradiance: list[float] = []
    temperature: list[float] = []
    for row in csv.DictReader(io.StringIO(text)):
        row_day = date(int(row["YEAR"]), int(row["MO"]), int(row["DY"]))
        if row_day != day:
            continue
        stamp = datetime(day.year, day.month, day.day, int(row["HR"]))
        stamps.append(stamp)
        irradiance.append(_value(row["ALLSKY_SFC_SW_DWN"], "irradiance", _label(stamp)))
        temperature.append(_value(row["T2M"], "temperature", _label(stamp)))

    start = datetime(day.year, day.month, day.day)
    expected = [start + timedelta(hours=hour) for hour in range(24)]
    if stamps != expected:
        raise ProfileError(
            f"{day}: expected 24 consecutive hourly rows from 00:00 to 23:00, found {len(stamps)}"
        )
    return _series(stamps, irradiance, temperature, name=f"Bundled {day.isoformat()}")


def load_bundled_profile(day: date) -> Profile:
    """Load one day from the sample bundled with the package."""
    text = (files("pvysics") / "data" / BUNDLED_CSV).read_text(encoding="utf-8")
    return parse_profile_csv(text, day)


def csv_columns(text: str) -> list[str]:
    """The header names of a CSV file, in file order."""
    header = next(csv.reader(io.StringIO(text)), [])
    if not any(column.strip() for column in header):
        raise ProfileError("the file has no header row")
    return header


def guess_columns(header: list[str]) -> ColumnMap:
    """A starting column mapping from the common names. Inputs that match nothing are left empty."""
    timestamp = _first_match(header, TIMESTAMP_NAMES)
    if not timestamp and all(column in header for column in NASA_COLUMNS):
        timestamp = NASA_TIMESTAMP
    return ColumnMap(
        timestamp=timestamp,
        irradiance=_first_match(header, IRRADIANCE_NAMES),
        temperature=_first_match(header, TEMPERATURE_NAMES),
    )


def parse_profile_table(text: str, columns: ColumnMap, name: str = "") -> Profile:
    """Build a Profile from CSV text, reading the columns the mapping names.

    Times must increase, step by one constant interval (no gaps), and be ISO date-times or the
    NASA POWER YEAR, MO, DY, HR columns. Each value must be a finite number, not -999, and
    irradiance must not be negative.
    """
    header = csv_columns(text)
    _check_mapping(header, columns)
    stamps: list[datetime] = []
    irradiance: list[float] = []
    temperature: list[float] = []
    reader = csv.DictReader(io.StringIO(text))
    for number, row in enumerate(reader, start=1):
        where = f"row {number}"
        stamps.append(_stamp(row, columns.timestamp, where))
        irradiance.append(_value(row.get(columns.irradiance), "irradiance", where))
        temperature.append(_value(row.get(columns.temperature), "temperature", where))
    return _series(stamps, irradiance, temperature, name=name)


def _check_mapping(header: list[str], columns: ColumnMap) -> None:
    if columns.timestamp == NASA_TIMESTAMP:
        required = NASA_COLUMNS
    else:
        required = (columns.timestamp,)
    for role, column in (
        ("timestamp", columns.timestamp),
        ("irradiance", columns.irradiance),
        ("temperature", columns.temperature),
    ):
        if not column:
            raise ProfileError(f"no column is chosen for {role}")
    for column in (*required, columns.irradiance, columns.temperature):
        if column not in header:
            raise ProfileError(
                f"missing column '{column}'; the file has: {', '.join(header)}"
            )
    if columns.irradiance == columns.temperature:
        raise ProfileError("irradiance and temperature must come from different columns")


def _stamp(row: dict, column: str, where: str) -> datetime:
    if column == NASA_TIMESTAMP:
        try:
            return datetime(int(row["YEAR"]), int(row["MO"]), int(row["DY"]), int(row["HR"]))
        except (TypeError, ValueError) as error:
            raise ProfileError(f"{where}: YEAR, MO, DY, HR is not a valid date and hour") from error
    text = (row.get(column) or "").strip()
    try:
        stamp = datetime.fromisoformat(text)
    except ValueError as error:
        raise ProfileError(f"{where}: timestamp '{text}' is not an ISO date and time") from error
    return stamp.replace(tzinfo=None)


def _series(
    stamps: list[datetime],
    irradiance: list[float],
    temperature: list[float],
    name: str,
) -> Profile:
    """The checks shared by every source: order, no gaps, no negative irradiance."""
    if len(stamps) < 2:
        raise ProfileError("the profile needs at least two rows")
    steps = [later - earlier for earlier, later in zip(stamps, stamps[1:])]
    for index, step in enumerate(steps, start=1):
        if step <= timedelta(0):
            raise ProfileError(f"{_label(stamps[index])}: time does not increase after the row before")
    expected = steps[0]
    for index, step in enumerate(steps, start=1):
        if step != expected:
            raise ProfileError(
                f"{_label(stamps[index])}: gap in the time steps, the step is {step} "
                f"but the first step is {expected}"
            )
    for stamp, value in zip(stamps, irradiance):
        if value < 0.0:
            raise ProfileError(f"{_label(stamp)}: irradiance is negative")
    return Profile(
        timestamps=np.array(stamps, dtype="datetime64[s]"),
        irradiance=np.array(irradiance, dtype=np.float64),
        temperature=np.array(temperature, dtype=np.float64),
        name=name,
    )


def _value(text: str | None, name: str, where: str) -> float:
    if text is None or not text.strip():
        raise ProfileError(f"{where}: {name} is missing")
    try:
        value = float(text)
    except ValueError as error:
        raise ProfileError(f"{where}: {name} '{text}' is not a number") from error
    if value == MISSING_VALUE:
        raise ProfileError(f"{where}: {name} is the missing-value marker -999")
    if not math.isfinite(value):
        raise ProfileError(f"{where}: {name} is not finite")
    return value


def _label(stamp: datetime) -> str:
    return stamp.isoformat(sep=" ", timespec="minutes")


def _first_match(header: list[str], names: tuple[str, ...]) -> str:
    lowered = {column.lower(): column for column in header}
    for name in names:
        if name.lower() in lowered:
            return lowered[name.lower()]
    return ""
