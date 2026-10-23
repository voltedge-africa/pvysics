"""The command line: which windows open at start. Pure: it parses argv and starts no Qt.

No switch opens the launcher. --hmi, --dashboard and --both open those windows and no launcher.
The switches exclude each other; an unknown switch or a conflict prints usage and exits non-zero.
"""

import argparse
from collections.abc import Sequence

LAUNCHER = "launcher"
HMI = "hmi"
DASHBOARD = "dashboard"
BOTH = "both"


def parse_opening(argv: Sequence[str]) -> str:
    """The windows to open for argv: LAUNCHER, HMI, DASHBOARD or BOTH."""
    parser = argparse.ArgumentParser(
        prog="pvysics",
        description="PV Digital Twin. With no switch, the launcher opens.",
    )
    choice = parser.add_mutually_exclusive_group()
    choice.add_argument("--hmi", dest="opening", action="store_const", const=HMI, help="open only the HMI")
    choice.add_argument(
        "--dashboard", dest="opening", action="store_const", const=DASHBOARD, help="open only the Dashboard"
    )
    choice.add_argument("--both", dest="opening", action="store_const", const=BOTH, help="open the HMI and the Dashboard")
    parser.set_defaults(opening=LAUNCHER)
    return parser.parse_args(list(argv)).opening
