#!/usr/bin/env python3
"""Generate assets/sahkoposti.png (the click package icon).

The icon is an envelope in the project's accent green on a purple background:
a rounded outline with the two folds of the flap drawn in the same, heavy
line. Read from the top it is also the letter "M" - the two side walls are
its stems and the flap is its middle.

The drawing lives in the numbers below; the SVG next to this script is the
same picture in vector form and that is the file the launcher reads (`Icon=`
in the desktop file). The PNG is what the click manifest points at.

    python3 tools/make-icon.py

Copyright (C) 2026 Reijo Kinnunen - SPDX-License-Identifier: GPL-3.0-or-later
"""

import os

from PIL import Image, ImageDraw

SIZE = 256
BACKGROUND = (119, 33, 111, 255)      # #77216F - Ubuntu purple
GREEN = (62, 179, 79, 255)            # #3EB34F - the project's accent green
BACKGROUND_RADIUS = 56

ENVELOPE_BOX = [46, 70, 210, 186]     # left, top, right, bottom
ENVELOPE_RADIUS = 16
STROKE = 20                           # one weight for the whole drawing
FLAP = [(60, 84), (128, 142), (196, 84)]   # the folds, from corner to corner


def main():
    image = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    draw.rounded_rectangle(
        [0, 0, SIZE - 1, SIZE - 1], radius=BACKGROUND_RADIUS, fill=BACKGROUND
    )
    draw.rounded_rectangle(
        ENVELOPE_BOX,
        radius=ENVELOPE_RADIUS,
        outline=GREEN,
        width=STROKE,
    )

    # The folds, drawn with round ends and a round corner in the middle so the
    # bitmap matches the SVG's stroke-linecap/linejoin.
    radius = STROKE // 2
    for start, end in zip(FLAP, FLAP[1:]):
        draw.line([start, end], fill=GREEN, width=STROKE)
    for point in FLAP:
        draw.ellipse(
            [
                point[0] - radius,
                point[1] - radius,
                point[0] + radius,
                point[1] + radius,
            ],
            fill=GREEN,
        )

    target = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "assets",
        "sahkoposti.png",
    )
    image.save(target, "PNG", optimize=True)
    print("wrote %s (%d bytes)" % (target, os.path.getsize(target)))


if __name__ == "__main__":
    main()
