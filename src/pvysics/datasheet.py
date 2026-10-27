"""Module datasheet: the nameplate values the Single Diode Model is derived from.

Two file formats are read: the TOML format of the bundled generic module, and JSON with the
datasheet keys Isc, Voc, Impp, Vmpp, Ki, Kv and Ns. A malformed or incomplete file is rejected
with a DatasheetError that says what is wrong. The file is never partly applied.
"""

import csv
import io
import json
import math
import re
import tomllib
import zipfile
from dataclasses import dataclass, replace
from importlib.resources import files
from pathlib import Path

from pvysics.spreadsheet import CSV_SUFFIX, XLSX_SUFFIX, SpreadsheetError, write_table, xlsx_to_csv_text

GENERIC_DATASHEET = "generic_60cell_250w.toml"
CUSTOM_MODULE_NAME = "Custom module"  # the name of a module whose values the user has edited
JSON_KEYS = {
    "Isc": "isc_a",
    "Voc": "voc_v",
    "Impp": "impp_a",
    "Vmpp": "vmpp_v",
    "Ki": "ki_pct_per_c",
    "Kv": "kv_pct_per_c",
    "Ns": "ns",
}
JSON_NAMES = {field: key for key, field in JSON_KEYS.items()}  # field to key, for messages
REQUIRED_FIELDS = ("name", "ns", "isc_a", "voc_v", "impp_a", "vmpp_v", "ki_pct_per_c", "kv_pct_per_c")
POSITIVE_FIELDS = ("isc_a", "voc_v", "impp_a", "vmpp_v", "pmpp_w")


# The datasheet template: one parameter per row. A CSV or Excel datasheet is read from the first two columns, the
# parameter and its value; the unit and notes columns are for the person filling it in. The values are the bundled
# generic module's, to be replaced.
TEMPLATE_HEADER = ("parameter", "value", "unit", "notes")
TEMPLATE_ROWS = (
    ("name", "My module", "", "A label for this module"),
    ("Isc", 8.9, "A", "Short-circuit current at standard test conditions (STC)"),
    ("Voc", 37.8, "V", "Open-circuit voltage at STC"),
    ("Impp", 8.3, "A", "Current at maximum power. Must be below Isc"),
    ("Vmpp", 30.1, "V", "Voltage at maximum power. Must be below Voc"),
    ("Ki", 0.05, "%/C", "Temperature coefficient of Isc, in percent per degree C"),
    ("Kv", -0.32, "%/C", "Temperature coefficient of Voc, in percent per degree C (negative)"),
    ("Ns", 60, "cells", "Cells in series, a whole number"),
)
TEMPLATE_NOTES = (
    ("Row", "What to do"),
    ("Parameters", "Put your module's values in the value column. Keep the parameter names in the first column."),
    ("Optional", "You may add a row named Pmpp (rated power in W). Without it the app uses Vmpp times Impp."),
    ("Where from", "All values are on the module's datasheet, at standard test conditions (1000 W/m2, 25 C)."),
    ("Units", "Currents in A, voltages in V, temperature coefficients in %/C. Do not write units in the value cells."),
)
TABLE_KEYS = {  # a parameter name as written, lower case with spaces as underscores, to the datasheet field
    "name": "name",
    "ns": "ns",
    "cells": "ns",
    "isc": "isc_a",
    "isc_a": "isc_a",
    "voc": "voc_v",
    "voc_v": "voc_v",
    "impp": "impp_a",
    "impp_a": "impp_a",
    "vmpp": "vmpp_v",
    "vmpp_v": "vmpp_v",
    "ki": "ki_pct_per_c",
    "ki_pct_per_c": "ki_pct_per_c",
    "kv": "kv_pct_per_c",
    "kv_pct_per_c": "kv_pct_per_c",
    "pmpp": "pmpp_w",
    "pmpp_w": "pmpp_w",
}


class DatasheetError(ValueError):
    """The datasheet file is malformed, incomplete or not a module that can be modelled."""


@dataclass(frozen=True)
class ModuleDatasheet:
    name: str
    ns: int  # cells in series
    pmpp_w: float  # rated power at standard test conditions
    isc_a: float
    voc_v: float
    impp_a: float
    vmpp_v: float
    ki_pct_per_c: float  # temperature coefficient of Isc
    kv_pct_per_c: float  # temperature coefficient of Voc


def edited_datasheet(datasheet: ModuleDatasheet, **values: float | int) -> ModuleDatasheet:
    """The datasheet with edited values, named Custom module. Its Pmpp is Vmpp times Impp.

    The values are not checked here: see run_setup.datasheet_problems.
    """
    edited = replace(datasheet, **values)
    return replace(edited, name=CUSTOM_MODULE_NAME, pmpp_w=edited.vmpp_v * edited.impp_a)


def load_generic_datasheet() -> ModuleDatasheet:
    """Load the generic 60-cell, 250 W module bundled with the package."""
    text = (files("pvysics") / "data" / GENERIC_DATASHEET).read_text(encoding="utf-8")
    return ModuleDatasheet(**tomllib.loads(text))


def load_datasheet(path: str | Path) -> ModuleDatasheet:
    """Read a .toml or .json module datasheet. A JSON module is named after its file."""
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".toml":
        values = _toml_values(path)
    elif suffix == ".json":
        values = _json_values(path)
    elif suffix in (CSV_SUFFIX, XLSX_SUFFIX):
        values = _table_values(path)
    else:
        raise DatasheetError(f"{path.name}: the datasheet must be a .xlsx, .csv, .json or .toml file")
    datasheet = _module(values, path.name, names=JSON_NAMES if suffix != ".toml" else {})
    # Imported here because single_diode imports this module; a module that cannot be fitted is malformed.
    from pvysics.single_diode import fit_parameters

    try:
        fit_parameters(datasheet)
    except ValueError as error:
        raise DatasheetError(f"{path.name}: the values do not describe a module that can be modelled") from error
    return datasheet


def write_datasheet_template(path: str | Path) -> None:
    """Write the datasheet template as .csv or .xlsx, by the path's suffix. The workbook also has an Instructions sheet."""
    try:
        write_table(Path(path), TEMPLATE_HEADER, TEMPLATE_ROWS, TEMPLATE_NOTES, sheet="Datasheet")
    except SpreadsheetError as error:
        raise DatasheetError(f"the template is a .csv or .xlsx file, not '{Path(path).suffix}'") from error


def _table_values(path: Path) -> dict:
    """The datasheet fields of a CSV or Excel table of parameter and value rows. The name defaults to the file's."""
    try:
        text = _read_text(path) if path.suffix.lower() == CSV_SUFFIX else xlsx_to_csv_text(path)
    except (OSError, zipfile.BadZipFile, SpreadsheetError) as error:
        raise DatasheetError(f"{path.name}: cannot read the file ({error})") from error
    rows = [row for row in csv.reader(io.StringIO(text)) if any(cell.strip() for cell in row)]
    if rows and rows[0][0].strip().lower() == "parameter":
        rows = rows[1:]  # the header row
    values: dict = {"name": path.stem}
    for row in rows:
        field = TABLE_KEYS.get(re.sub(r"\(.*?\)", "", row[0]).strip().lower().replace(" ", "_"))
        if field is None:
            continue  # a row that is not a datasheet value, such as a note
        cell = row[1].strip() if len(row) > 1 else ""
        values[field] = cell if field == "name" else _table_number(cell, row[0].strip(), path.name, whole=field == "ns")
    return values


def _table_number(cell: str, parameter: str, file_name: str, whole: bool) -> float | int:
    try:
        number = float(cell)
    except ValueError as error:
        raise DatasheetError(f"{file_name}: {parameter} must be a number, got {cell!r}") from error
    return int(number) if whole and number.is_integer() else number


def _toml_values(path: Path) -> dict:
    try:
        values = tomllib.loads(_read_text(path))
    except tomllib.TOMLDecodeError as error:
        raise DatasheetError(f"{path.name}: not valid TOML ({error})") from error
    return values


def _json_values(path: Path) -> dict:
    try:
        data = json.loads(_read_text(path))
    except json.JSONDecodeError as error:
        raise DatasheetError(f"{path.name}: not valid JSON (line {error.lineno}: {error.msg})") from error
    if not isinstance(data, dict):
        raise DatasheetError(f"{path.name}: expected a JSON object with the datasheet keys")
    missing = [key for key in JSON_KEYS if key not in data]
    if missing:
        raise DatasheetError(f"{path.name}: missing {', '.join(missing)}")
    values = {field: data[key] for key, field in JSON_KEYS.items()}
    values["name"] = path.stem
    return values


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8-sig")  # -sig also accepts a byte-order mark, as Windows editors add
    except (OSError, UnicodeDecodeError) as error:
        raise DatasheetError(f"{path.name}: cannot read the file as text ({error})") from error


def _module(values: dict, file_name: str, names: dict[str, str]) -> ModuleDatasheet:
    """Check every field and build the datasheet. pmpp_w defaults to Vmpp times Impp.

    `names` gives the key a field was written as in the file, so messages name what the user wrote.
    """
    key = {field: names.get(field, field) for field in REQUIRED_FIELDS + POSITIVE_FIELDS}
    missing = [key[field] for field in REQUIRED_FIELDS if field not in values]
    if missing:
        raise DatasheetError(f"{file_name}: missing {', '.join(missing)}")
    if not isinstance(values["name"], str) or not values["name"].strip():
        raise DatasheetError(f"{file_name}: name must be text")
    ns = values["ns"]
    if isinstance(ns, bool) or not isinstance(ns, int) or ns < 1:
        raise DatasheetError(f"{file_name}: {key['ns']} must be a whole number of cells, 1 or more")
    for field in ("ki_pct_per_c", "kv_pct_per_c"):
        _number(values[field], key[field], file_name)
    for field in POSITIVE_FIELDS:
        if field in values:
            _positive(values[field], key[field], file_name)
    if values["impp_a"] >= values["isc_a"]:
        raise DatasheetError(f"{file_name}: {key['impp_a']} must be below {key['isc_a']}")
    if values["vmpp_v"] >= values["voc_v"]:
        raise DatasheetError(f"{file_name}: {key['vmpp_v']} must be below {key['voc_v']}")
    pmpp_w = values.get("pmpp_w", values["vmpp_v"] * values["impp_a"])
    return ModuleDatasheet(
        name=values["name"],
        ns=ns,
        pmpp_w=float(pmpp_w),
        isc_a=float(values["isc_a"]),
        voc_v=float(values["voc_v"]),
        impp_a=float(values["impp_a"]),
        vmpp_v=float(values["vmpp_v"]),
        ki_pct_per_c=float(values["ki_pct_per_c"]),
        kv_pct_per_c=float(values["kv_pct_per_c"]),
    )


def _number(value: object, field: str, file_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise DatasheetError(f"{file_name}: {field} must be a number, got {value!r}")
    return float(value)


def _positive(value: object, field: str, file_name: str) -> float:
    number = _number(value, field, file_name)
    if number <= 0.0:
        raise DatasheetError(f"{file_name}: {field} must be above zero, got {value!r}")
    return number
