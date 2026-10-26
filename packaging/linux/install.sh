#!/bin/sh
# Install pvysics for the current user (or system-wide with PREFIX=/opt sudo ./install.sh). No Python needed.
set -e
here=$(cd "$(dirname "$0")" && pwd)
prefix=${PREFIX:-$HOME/.local/share}
mkdir -p "$prefix"
rm -rf "$prefix/pvysics"
cp -r "$here/pvysics" "$prefix/pvysics"
cp "$here/pvysics.png" "$prefix/pvysics.png"
if [ "$(id -u)" = 0 ]; then apps=/usr/share/applications; bin=/usr/local/bin; else apps=$HOME/.local/share/applications; bin=$HOME/.local/bin; fi
mkdir -p "$apps" "$bin"
sed "s|@PREFIX@|$prefix|g" "$here/pvysics.desktop" > "$apps/pvysics.desktop"
ln -sf "$prefix/pvysics/pvysics" "$bin/pvysics"
echo "Installed to $prefix/pvysics. Start it from the application menu or run: pvysics"
