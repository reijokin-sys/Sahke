#!/bin/sh
# Sähke - mail client for Ubuntu Touch
# Copyright (C) 2026 Reijo Kinnunen
# SPDX-License-Identifier: GPL-3.0-or-later
# Build the Sähke click package into dist/.
#
#   tools/build.sh
#
# The click tool comes from the Ubuntu archive:  sudo apt install click
# The package is pure QML + Python (architecture "all"), so no cross
# compilation and no Ubuntu Touch SDK container are needed.
set -eu

PROJECT=$(cd "$(dirname "$0")/.." && pwd)
cd "$PROJECT"

# Prefer a system wide click; otherwise use the unpacked copy in /tmp, which
# tools/click-host.sh creates on its first run (see the comment there).
if command -v click >/dev/null 2>&1; then
    CLICK=click
else
    CLICK="$PROJECT/tools/click-host.sh"
fi

# Keep the bitmap icon in step with its SVG source.
python3 tools/make-icon.py

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

# The package is assembled from an explicit file list, so nothing that only
# belongs to the repository (docs, tests, the helper scripts, the git data)
# can end up inside the click. The modes are normalised as well: the
# repository uses group write, which the store package has no use for.
stage="$work/package"
mkdir -p "$stage"
cp manifest.json fi.reijo.sahkoposti.apparmor sahkoposti.desktop mail.py \
    credentials.py LICENSE THIRD_PARTY_NOTICES.md "$stage/"
# `Lomiri` carries the app's own theme modules. They belong in the click's
# root - not under `qml/` - because the toolkit's theme loader finds them on
# the QML import paths and qmlscene looks in the working directory, which for
# a click is the click root.
cp -r qml assets Lomiri "$stage/"
chmod -R u=rwX,go=rX "$stage"

cd "$work"
"$CLICK" build --no-validate "$stage"

rm -rf "$PROJECT/dist"
mkdir -p "$PROJECT/dist"
mv "$work"/*.click "$PROJECT/dist/"

echo "--- built:"
ls -l "$PROJECT/dist/"
