/*
 * Sähke - mail client for Ubuntu Touch
 * Copyright (C) 2026 Reijo Kinnunen
 *
 * SPDX-License-Identifier: GPL-3.0-or-later
 */

.pragma library

/*
 * The same readable text scale as Puhuri.
 *
 * Lomiri's Label, Button and TextField take their pixel size from
 * `FontUtils.sizeToPixels(<name>)`; on this phone "medium" is 28 px, which
 * the user found a little hard to read. Every size goes through `bigger()`
 * with the same 1.15 factor Puhuri uses, so the relative sizes stay what
 * the toolkit intends and the whole app grows together.
 */
var SCALE = 1.15

function bigger(pixels) {
    return Math.round(pixels * SCALE)
}

/*
 * The message body and the compose field get one step more than the rest -
 * the same 1.07 that Puhuri uses for the text the user reads most.
 */
var MESSAGE_SCALE = 1.07

function message(pixels) {
    return Math.round(pixels * SCALE * MESSAGE_SCALE)
}
