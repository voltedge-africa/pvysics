"""Module datasheet: the nameplate values the Single Diode Model is derived from."""

import tomllib
from dataclasses import dataclass
from importlib.resources import files

GENERIC_DATASHEET = "generic_60cell_250w.toml"


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
