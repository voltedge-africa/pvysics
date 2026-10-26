"""Entry point PyInstaller freezes; the installed app starts here exactly as `pvysics` does."""

import sys

from pvysics.gui.app import main

if __name__ == "__main__":
    sys.exit(main())
