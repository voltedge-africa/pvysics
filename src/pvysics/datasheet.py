"""Module datasheet: the nameplate values the Single Diode Model is derived from.

Two file formats are read: the TOML format of the bundled generic module, and JSON with the
datasheet keys Isc, Voc, Impp, Vmpp, Ki, Kv and Ns. A malformed or incomplete file is rejected
with a DatasheetError that says what is wrong. The file is never partly applied.
"""

import json
import math
import tomllib
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path

GENERIC_DATASHEET = "generic_60cell_250w.toml"
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
    else:
        raise DatasheetError(f"{path.name}: the datasheet must be a .json or .toml file")
    datasheet = _module(values, path.name, names=JSON_NAMES if suffix == ".json" else {})
    # Imported here because single_diode imports this module; a module that cannot be fitted is malformed.
    from pvysics.single_diode import fit_parameters

    try:
        fit_parameters(datasheet)
    except ValueError as error:
        raise DatasheetError(f"{path.name}: the values do not describe a module that can be modelled") from error
    return datasheet


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
        return path.read_text(encoding="utf-8")
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
