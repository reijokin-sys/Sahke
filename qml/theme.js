/*
 * Sähke - mail client for Ubuntu Touch
 * Copyright (C) 2026 Reijo Kinnunen
 *
 * SPDX-License-Identifier: GPL-3.0-or-later
 */

.pragma library

/*
 * Sähke's own themes.
 *
 * The app does not follow the phone's theme: it picks one of its own three
 * modules (`Lomiri.Components.Themes.Sahkoposti*`) and the choice is the
 * user's (Settings). The modules ship inside the click, so the app looks the
 * same on every phone. This is the same mechanism and the same Revontuli
 * colours shared with the Puhuri project.
 *
 * The choice is stored by `Main.qml`'s `Qt.labs.settings` object
 * (`~/.config/fi.reijo.sahkoposti/theme.conf`), which reads it before the
 * first page is drawn and writes it when it changes.
 */

var DEFAULT_KEY = "sininen"

var THEMES = [
    { key: "punainen", module: "Lomiri.Components.Themes.SahkopostiPunainen" },
    { key: "vihrea", module: "Lomiri.Components.Themes.SahkopostiVihrea" },
    { key: "sininen", module: "Lomiri.Components.Themes.SahkopostiSininen" }
]

/// The module that belongs to one choice. An unknown key falls back to the
/// default theme, so a broken settings file cannot leave the app without one.
function moduleFor(key) {
    for (var i = 0; i < THEMES.length; i++)
        if (THEMES[i].key === key)
            return THEMES[i].module
    return moduleFor(DEFAULT_KEY)
}
