# Third-party notices

Sähke's own code is **GPL-3.0-or-later**; every own source file carries an
SPDX line. The click also ships the theme files below.

| What | Where it lives | Licence | Verified |
| --- | --- | --- | --- |
| **Sähke's theme modules** (`SahkopostiPunainen`, `SahkopostiVihrea`, `SahkopostiPerus`) - the `.qml` files | `Lomiri/Components/Themes/`, shipped **inside the click**; generated from Canonical Ltd.'s Lomiri theme files | **LGPL-3.0-only** (Canonical Ltd.'s Lomiri theme files; the colours are Sähke's modifications) | 2026-10-20: the files keep Canonical's LGPL header, each `.qml` carries an SPDX line **and a dated note of the modification** (module/type/file names and palette values), and the LGPL-3.0 text travels with them (`Lomiri/Components/Themes/LICENSE.LGPL-3.0`). Canonical's header says "version 3", and the Ubuntu `lomiri-ui-toolkit-theme` copyright says `License: LGPL-3`; LGPL-3.0-only section 3 allows use under GPL-3.0 |
| **Chevron artwork** (`chevron@27.png`) | `Lomiri/Components/Themes/*/artwork/`, shipped **inside the click** | **CC-BY-SA-3.0**, Copyright 2004-2013 Canonical Ltd. | 2026-10-20: byte-identical to the stock `SuruDark/artwork/chevron@27.png`; the Ubuntu package copyright lists that file under `CC-BY-SA-3.0`, not LGPL. Official text: `Lomiri/Components/Themes/LICENSE.CC-BY-SA-3.0`, source <https://creativecommons.org/licenses/by-sa/3.0/>. The PNG is a separate work and is not relicensed under GPL/LGPL |
| Lomiri/Ubuntu Touch components | the device's own system | their own licences | not our distribution |

The full GPL-3.0 text is `LICENSE`; the LGPL-3.0 and CC-BY-SA-3.0 texts
travel with the theme modules. The CC-BY-SA-3.0 attribution names Canonical
Ltd. as the copyright holder and keeps the artwork separate from Sähke's
GPL code. This is a maintainer's note, not legal advice.
