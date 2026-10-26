#!/bin/sh
# Test, build and checksum the installable app on this machine. Upload the files in dist/ to a git release.
set -e
cd "$(dirname "$0")/.."
uv run pytest -q
uv run --group build python packaging/build.py
cd dist
for file in *.tar.gz *.zip *.dmg *-setup.exe; do
    [ -f "$file" ] && sha256sum "$file" 2>/dev/null || shasum -a 256 "$file" 2>/dev/null || true
done | tee SHA256SUMS
echo "Upload to a release, for example: gh release create v$(grep -m1 '^version' ../pyproject.toml | cut -d'"' -f2) dist/*.tar.gz dist/*.zip dist/*.dmg dist/*-setup.exe dist/SHA256SUMS"
