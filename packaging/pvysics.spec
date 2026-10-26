# PyInstaller spec: a one-folder app with the Python runtime, Qt and every data file the package reads.
# Build with `uv run python packaging/build.py`; it renders the icon this spec needs first.
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files

root = Path(SPECPATH).parent
icon = {"win32": "icon.ico", "darwin": "icon.icns"}.get(sys.platform, "icon.png")

a = Analysis(
    [str(root / "packaging" / "entry.py")],
    pathex=[str(root / "src")],
    datas=collect_data_files("pvysics"),  # assets, fonts, qml, data: pvysics reads them from beside its modules
    hiddenimports=["PyQt6.QtSvg", "PyQt6.QtQuick", "PyQt6.QtQml"],
    excludes=["tkinter", "pytest", "pytestqt"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="pvysics",
    console=False,
    icon=str(root / "build" / "icons" / icon),
)
coll = COLLECT(exe, a.binaries, a.datas, name="pvysics")
if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="pvysics.app",
        icon=str(root / "build" / "icons" / "icon.icns"),
        bundle_identifier="com.pvysics.app",
        info_plist={"NSHighResolutionCapable": True, "CFBundleDisplayName": "PV Digital Twin"},
    )
