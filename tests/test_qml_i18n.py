#!/usr/bin/env python3
# Sähke - mail client for Ubuntu Touch
# Copyright (C) 2026 Reijo Kinnunen
#
# SPDX-License-Identifier: GPL-3.0-or-later
"""The QML language selector and translation table are wired up."""

import os
import re
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(path):
    with open(os.path.join(ROOT, path), "r", encoding="utf-8") as handle:
        return handle.read()


class QmlLanguageTests(unittest.TestCase):
    def test_translation_table_has_both_languages_and_defaults_to_english(self):
        i18n = read("qml/i18n.js")
        self.assertIn('defaultLanguage = "en"', i18n)
        self.assertIn('"en": {', i18n)
        self.assertIn('"fi": {', i18n)
        for key in (
            "settings.language",
            "settings.languageEnglish",
            "settings.languageFinnish",
            "inbox.title",
            "message.reply",
            "compose.send",
            "trash.title",
            "dialog.close",
        ):
            self.assertIn('"%s":' % key, i18n)

    def test_settings_exposes_language_choice(self):
        settings = read("qml/SettingsPage.qml")
        self.assertIn("signal languageRequested", settings)
        self.assertIn('tr("settings.languageEnglish")', settings)
        self.assertIn('tr("settings.languageFinnish")', settings)

    def test_main_owns_and_persists_the_language(self):
        main = read("qml/Main.qml")
        self.assertIn("property string language", main)
        self.assertIn('mail.set_language', main)
        self.assertIn('mail.language', main)
        self.assertIn("language: root.language", main)

    def test_both_languages_have_the_same_keys_and_qml_uses_existing_keys(self):
        i18n = read("qml/i18n.js")
        blocks = {}
        for language in ("en", "fi"):
            match = re.search(
                r'"%s": \{(.*?)\n    \}' % language, i18n, re.S
            )
            self.assertIsNotNone(match, language)
            blocks[language] = set(
                re.findall(r'^\s{8}"([^"]+)":', match.group(1), re.M)
            )
        self.assertEqual(blocks["en"], blocks["fi"])
        self.assertGreater(len(blocks["en"]), 50)

        used = set()
        for name in os.listdir(os.path.join(ROOT, "qml")):
            if not name.endswith(".qml"):
                continue
            text = read(os.path.join("qml", name))
            used.update(re.findall(r'(?:page\.|root\.)?tr\("([^"]+)"\)', text))
        self.assertTrue(used)
        self.assertEqual(used - blocks["en"], set())


if __name__ == "__main__":
    unittest.main()
