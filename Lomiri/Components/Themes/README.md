# Sähke's theme modules

This directory contains the three theme modules shipped with Sähke:

| Directory | Theme |
| --- | --- |
| `SahkopostiPunainen/` | Revontuli red (default) |
| `SahkopostiVihrea/` | Revontuli green |
| `SahkopostiPerus/` | base theme the two variants build on |

The QML files are derivatives of **Canonical Ltd.'s Lomiri theme files**.
They keep Canonical's copyright and licence notice, carry an SPDX line and
a dated note of the changes made for Sähke (module, type and file names,
and the palette values).

The `.qml` files are licensed **LGPL-3.0-only**. The full text is
`LICENSE.LGPL-3.0` in this directory. LGPL-3.0-only section 3 allows the
files to be used under GPL-3.0, which is the licence of Sähke's own code.

The **chevron artwork** (`*/artwork/chevron@27.png`) is Canonical's
unmodified SuruDark file and is licensed **CC-BY-SA-3.0**, not LGPL. Its
official text is `LICENSE.CC-BY-SA-3.0`; the attribution is in
`THIRD_PARTY_NOTICES.md`. The PNG is a separate work and is not relicensed
under GPL/LGPL.

The modules are at the click's root, not under `qml/`, because the toolkit's
theme loader finds a module on the QML import paths and `qmlscene` looks in
the click's working directory.
