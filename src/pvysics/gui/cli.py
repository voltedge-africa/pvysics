"""The command line: which windows open at start. Pure: it parses argv and starts no Qt.

With no switch all three windows open (--all). --hmi, --dashboard and --sensors open one; --both opens the HMI and the Dashboard.
The switches exclude each other; an unknown switch or a conflict prints usage and exits non-zero.
"""

import argparse
from collections.abc import Sequence

HMI = "hmi"
DASHBOARD = "dashboard"
BOTH = "both"
SENSORS = "sensors"
ALL = "all"


def parse_opening(argv: Sequence[str]) -> str:
    """The windows to open for argv: HMI, DASHBOARD, SENSORS, BOTH (the HMI and the Dashboard) or ALL."""
    parser = argparse.ArgumentParser(
        prog="pvysics",
        description="PV Digital Twin. With no switch, the HMI, the Dashboard and the Sensors window open.",
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
