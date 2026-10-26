"""Build the installable app for the platform this runs on: icons, a frozen app, then an installer package.

    uv run --group build python packaging/build.py

Writes to dist/: a .tar.gz with an install script (Linux), a .zip plus an Inno Setup script (Windows) or a .dmg
(macOS). The result needs no Python on the target device. PyInstaller cannot cross-compile, so build on each
platform (run it on each machine).
"""

import os
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parent.parent
PACKAGING = ROOT / "packaging"
ICONS = ROOT / "build" / "icons"
DIST = ROOT / "dist"
NAME = "pvysics"
VERSION = next(line.split('"')[1] for line in (ROOT / "pyproject.toml").read_text().splitlines() if line.startswith("version"))


def render_icon() -> None:
    """icon.svg to a 1024 px PNG; Pillow (through PyInstaller) makes the .ico and .icns from it."""
    from PyQt6.QtGui import QGuiApplication, QImage, QPainter
    from PyQt6.QtSvg import QSvgRenderer

    app = QGuiApplication.instance() or QGuiApplication(sys.argv)
    renderer = QSvgRenderer(str(ROOT / "src" / "pvysics" / "gui" / "assets" / "icon.svg"))
    image = QImage(1024, 1024, QImage.Format.Format_ARGB32)
    image.fill(0)
    painter = QPainter(image)
    renderer.render(painter)
    painter.end()
    ICONS.mkdir(parents=True, exist_ok=True)
    image.save(str(ICONS / "icon.png"))
    from PIL import Image

    picture = Image.open(ICONS / "icon.png")
    picture.save(ICONS / "icon.ico", sizes=[(s, s) for s in (16, 32, 48, 64, 128, 256)])
    picture.save(ICONS / "icon.icns")
    del app


def freeze() -> None:
    subprocess.run(
        [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--distpath", str(DIST), "--workpath", str(ROOT / "build" / "work"), str(PACKAGING / "pvysics.spec")],
        check=True,
    )


def package_linux() -> Path:
    stage = DIST / f"{NAME}-{VERSION}-linux-x86_64"
    shutil.rmtree(stage, ignore_errors=True)
    stage.mkdir()
    shutil.copytree(DIST / NAME, stage / NAME)
    shutil.copy(ICONS / "icon.png", stage / f"{NAME}.png")
    shutil.copy(PACKAGING / "linux" / "install.sh", stage / "install.sh")
    shutil.copy(PACKAGING / "linux" / "pvysics.desktop", stage / "pvysics.desktop")
    (stage / "install.sh").chmod(0o755)
    archive = DIST / f"{stage.name}.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(stage, arcname=stage.name)
    return archive


def package_windows() -> Path:
    archive = shutil.make_archive(str(DIST / f"{NAME}-{VERSION}-windows"), "zip", DIST, NAME)
    iscc = shutil.which("iscc")
    if iscc:  # Inno Setup, when installed, also makes a one-file installer
        subprocess.run([iscc, f"/DVersion={VERSION}", str(PACKAGING / "windows" / "pvysics.iss")], check=True)
    return Path(archive)


def package_macos() -> Path:
    dmg = DIST / f"{NAME}-{VERSION}-macos.dmg"
    dmg.unlink(missing_ok=True)
    subprocess.run(["hdiutil", "create", "-volname", "pvysics", "-srcfolder", str(DIST / f"{NAME}.app"), "-ov", "-format", "UDZO", str(dmg)], check=True)
    return dmg


def main() -> None:
    shutil.rmtree(DIST, ignore_errors=True)
    render_icon()
    freeze()
    packager = {"linux": package_linux, "win32": package_windows, "darwin": package_macos}[sys.platform]
    print(f"built {packager()}")


if __name__ == "__main__":
    main()
