#!/bin/sh
# Build the Windows app (zip and setup exe) from Linux, inside a real Windows 11 container (dockurr/windows).
# Needs docker or podman, /dev/kvm, about 8 GB of RAM, 4 cores and 64 GB of disk. The first run installs Windows
# (about 25 minutes, downloaded from Microsoft, whose licence terms apply); later runs reuse it and take about 10.
# Output: dist/pvysics-<version>-windows.zip and dist/pvysics-<version>-windows-setup.exe.
set -e
cd "$(dirname "$0")/../../.."
ENGINE=${ENGINE:-$(command -v docker || command -v podman)}
WORK=${WORK:-$HOME/.cache/pvysics-winbuild}
STORAGE=${STORAGE:-$WORK/storage}  # the Windows disk; point it at an installed one to skip installing Windows
NAME=pvysics-win
mkdir -p "$STORAGE" "$WORK/shared" "$WORK/oem"
rm -rf "$WORK/shared/src-tree" "$WORK/shared/out" "$WORK/shared/DONE"
mkdir "$WORK/shared/src-tree"
git archive HEAD | tar -x -C "$WORK/shared/src-tree"
cp packaging/windows/vm/install.bat "$WORK/oem/install.bat"
cp packaging/windows/vm/build.bat "$WORK/shared/run.bat.initial"

if "$ENGINE" ps -q -f name=$NAME | grep -q .; then
    echo "Windows is running: queueing the build"
    cp packaging/windows/vm/build.bat "$WORK/shared/run.bat"  # the VM's scheduled task picks this up within a minute
else
    "$ENGINE" rm -f $NAME >/dev/null 2>&1 || true
    "$ENGINE" run -d --name $NAME -e VERSION=11 -e RAM_SIZE=8G -e CPU_CORES=4 -e DISK_SIZE=64G \
        -p 127.0.0.1:8006:8006 --device /dev/kvm --device /dev/net/tun --cap-add NET_ADMIN \
        -v "$STORAGE":/storage -v "$WORK/shared":/shared -v "$WORK/oem":/oem \
        --stop-timeout 120 dockurr/windows >/dev/null
    echo "Windows is starting. Watch at http://127.0.0.1:8006"
    # A fresh Windows runs run.bat.initial itself once installed. An installed one does not, so queue the build.
    [ -f "$STORAGE/data.img" ] && cp packaging/windows/vm/build.bat "$WORK/shared/run.bat"
fi

until [ -f "$WORK/shared/DONE" ]; do sleep 20; done
sleep 3
mkdir -p dist
cp "$WORK"/shared/out/* dist/
"$ENGINE" stop -t 120 $NAME >/dev/null
echo "built:"; ls -1 dist/*windows*
echo "The Windows VM is stopped, not deleted: the next run is faster. Remove it with: $ENGINE rm $NAME; rm -rf $WORK"
