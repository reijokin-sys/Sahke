#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later

import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
THEME_DIR = ROOT / "Lomiri/Components/Themes/SahkopostiSininen"


class BlueBlackThemeTest(unittest.TestCase):
    def test_theme_mapping_contains_the_third_theme(self):
        theme_js = (ROOT / "qml/theme.js").read_text()
        self.assertIn(
            '{ key: "sininen", module: "Lomiri.Components.Themes.SahkopostiSininen" }',
            theme_js,
        )

    def test_settings_offer_and_select_the_third_theme(self):
        settings = (ROOT / "qml/SettingsPage.qml").read_text()
        self.assertIn('tr("settings.themeBlue")', settings)
        self.assertIn('"sininen"', settings)

    def test_both_languages_name_the_theme(self):
        i18n = (ROOT / "qml/i18n.js").read_text()
        self.assertEqual(i18n.count('"settings.themeBlue":'), 2)
        self.assertIn('"settings.themeBlue": "Revontuli blue-black"', i18n)
        self.assertIn('"settings.themeBlue": "Revontuli sinimusta"', i18n)

    def test_bundled_module_contains_the_blue_black_palette(self):
        normal = (
            THEME_DIR / "1.3/SahkopostiSininenNormal.qml"
        ).read_text()
        selected = (
            THEME_DIR / "1.3/SahkopostiSininenSelected.qml"
        ).read_text()
        self.assertEqual((THEME_DIR / "parent_theme").read_text().strip(),
                         "Lomiri.Components.Themes.SahkopostiPerus")
        self.assertIn('background: "#000000"', normal)
        self.assertIn('baseText: "#4A9EFF"', normal)
        self.assertIn('background: "#4A9EFF"', selected)
        self.assertIn('baseText: "#000000"', selected)

    def test_normal_text_fields_are_lighter_black_with_blue_text(self):
        normal = (
            THEME_DIR / "1.3/SahkopostiSininenNormal.qml"
        ).read_text()
        self.assertIn('field: "#151515"', normal)
        self.assertIn('fieldText: "#4A9EFF"', normal)

    def test_12_palette_has_lighter_black_normal_text_fields(self):
        palette = (THEME_DIR / "1.2/Palette.qml").read_text()
        normal = palette.split("normal: PaletteValues {", 1)[1].split(
            "\n    }", 1
        )[0]
        self.assertIn('field: "#151515"', normal)
        self.assertIn('fieldText: "#4A9EFF"', normal)

    @unittest.skipUnless(
        (ROOT / "tools/sync-teemat.sh").is_file(),
        "the private theme source tool is not part of the public source tree",
    )
    def test_sync_script_reproduces_the_third_module(self):
        sync = (ROOT / "tools/sync-teemat.sh").read_text()
        self.assertIn(
            "copy_theme RevontuliMustavalkoinenSininen "
            "SahkopostiSininen RevontuliMustavalkoinenSininen SahkopostiSininen",
            sync,
        )
        self.assertIn(
            'echo "Lomiri.Components.Themes.SahkopostiPerus" '
            '>"$TARGET/SahkopostiSininen/parent_theme"',
            sync,
        )


if __name__ == "__main__":
    unittest.main()
