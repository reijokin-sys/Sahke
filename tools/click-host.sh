#!/bin/sh
# Sähke - mail client for Ubuntu Touch
# Copyright (C) 2026 Reijo Kinnunen
# SPDX-License-Identifier: GPL-3.0-or-later
# Run the Ubuntu "click" tool on this computer without installing it.
#
#   tools/click-host.sh build --no-validate -I .git .
#
# The tool is the same Ubuntu package the phone uses (click 0.5.2), but it is
# unpacked into /tmp/click-tool instead of being installed system wide: this
# machine has no root access for apt and "click" is not in the archive of the
# installed release for a plain user install.
#
# The first run downloads eight small packages from the Ubuntu archive and
# therefore needs network access (a minute at most); later runs work offline.
# CLICK_TOOL_DIR overrides the unpack directory.
#
# Everything after the tool name is passed straight to "click".
set -eu

TOOL_DIR=${CLICK_TOOL_DIR:-/tmp/click-tool}
ROOT="$TOOL_DIR/root"

PACKAGES="click python3-click-package libclick-0.4-0 gir1.2-click-0.4 \
gir1.2-json-1.0 libjson-glib-1.0-0 gir1.2-gee-0.8 libgee-0.8-2"

if [ ! -x "$ROOT/usr/bin/click" ]; then
    echo "--- unpacking the click tool into $TOOL_DIR (first run, needs the network)" >&2
    mkdir -p "$TOOL_DIR"
    (
        cd "$TOOL_DIR"
        # shellcheck disable=SC2086
        apt-get download $PACKAGES >/dev/null
    )
    for deb in "$TOOL_DIR"/*.deb; do
        dpkg-deb -x "$deb" "$ROOT"
    done
fi

# The architecture directory under usr/lib (x86_64-linux-gnu, aarch64-linux-gnu,
# ...) is discovered from the unpacked tree instead of guessed from the packaging
# architecture name, which is not the same string.
GIREPO=$(ls -d "$ROOT"/usr/lib/*/girepository-1.0 2>/dev/null | head -1)
[ -n "$GIREPO" ] || {
    echo "VIRHE: click-tyokalun purku nayi rikkiniselta ($ROOT)" >&2
    exit 1
}
LIBDIR=$(dirname "$GIREPO")

PYTHONPATH="$ROOT/usr/lib/python3/dist-packages${PYTHONPATH:+:$PYTHONPATH}" \
GI_TYPELIB_PATH="$GIREPO${GI_TYPELIB_PATH:+:$GI_TYPELIB_PATH}" \
LD_LIBRARY_PATH="$LIBDIR${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" \
exec python3 "$ROOT/usr/bin/click" "$@"
