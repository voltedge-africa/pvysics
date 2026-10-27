"""The command line and environment: which windows open at start. Pure: it reads argv and the environment and starts no Qt.

By default the app opens one simple window (SIMPLE) and takes no window switches. Setting PVYSICS_ADVANCED_VERSION
to 1, true, yes or on brings back the three-window app: with no switch all three windows open (--all). --hmi,
--dashboard and --sensors open one; --both opens the HMI and the Dashboard. The switches exclude each other; an
unknown switch or a conflict prints usage and exits non-zero.
"""

import argparse
import os
from collections.abc import Mapping, Sequence

ADVANCED_ENV = "PVYSICS_ADVANCED_VERSION"
_TRUE_VALUES = ("1", "true", "yes", "on")

SIMPLE = "simple"
HMI = "hmi"
DASHBOARD = "dashboard"
BOTH = "both"
SENSORS = "sensors"
ALL = "all"


def advanced_enabled(environ: Mapping[str, str] | None = None) -> bool:
    """True when PVYSICS_ADVANCED_VERSION asks for the advanced (HMI, Dashboard, Sensors) app. Unset or anything else is False."""
    value = (os.environ if environ is None else environ).get(ADVANCED_ENV, "")
    return value.strip().lower() in _TRUE_VALUES


def parse_opening(argv: Sequence[str], advanced: bool | None = None) -> str:
    """The windows to open for argv: SIMPLE, or with advanced HMI, DASHBOARD, SENSORS, BOTH (the HMI and the Dashboard) or ALL.

    advanced defaults to advanced_enabled(). The simple app has no window switches, so any switch is a usage error."""
    advanced = advanced_enabled() if advanced is None else advanced
    if not advanced:
        parser = argparse.ArgumentParser(
            prog="pvysics",
            description=f"PV Digital Twin. Set {ADVANCED_ENV}=1 for the advanced version: the HMI, the Dashboard and "
            "the Sensors window, with the --hmi, --dashboard, --sensors, --all and --both switches.",
        )
        parser.parse_args(list(argv))
        return SIMPLE
    parser = argparse.ArgumentParser(
        prog="pvysics",
        description="PV Digital Twin, advanced version. With no switch, the HMI, the Dashboard and the Sensors window open.",
    )
    choice = parser.add_mutually_exclusive_group()
    choice.add_argument("--hmi", dest="opening", action="store_const", const=HMI, help="open only the HMI")
    choice.add_argument(
        "--dashboard", dest="opening", action="store_const", const=DASHBOARD, help="open only the Dashboard"
    )
    choice.add_argument("--sensors", dest="opening", action="store_const", const=SENSORS, help="open only the Sensors window")
    choice.add_argument("--all", dest="opening", action="store_const", const=ALL, help="open all three windows (the default)")
    choice.add_argument("--both", dest="opening", action="store_const", const=BOTH, help="open the HMI and the Dashboard")
    parser.set_defaults(opening=ALL)
    return parser.parse_args(list(argv)).opening
