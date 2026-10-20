#!/usr/bin/env python3
# Sähke - mail client for Ubuntu Touch
# Copyright (C) 2026 Reijo Kinnunen
#
# SPDX-License-Identifier: GPL-3.0-or-later
"""The sign-out action is wired from Settings to the backend."""

import os
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(path):
    with open(os.path.join(ROOT, path), "r", encoding="utf-8") as handle:
        return handle.read()


class QmlLogoutTests(unittest.TestCase):
    def test_logout_strings_exist(self):
        i18n = read("qml/i18n.js")
        for key in (
            "settings.logout",
            "dialog.logout.title",
            "dialog.logout.text",
            "dialog.logout.cancel",
            "dialog.logout.confirm",
            "notice.signedOut",
        ):
            self.assertIn('"%s":' % key, i18n)

    def test_settings_exposes_logout(self):
        settings = read("qml/SettingsPage.qml")
        self.assertIn("signal logoutRequested", settings)
        self.assertIn('page.tr("settings.logout")', settings)

    def test_main_calls_backend_logout(self):
        main = read("qml/Main.qml")
        self.assertIn("mail.logout", main)
        self.assertIn("onLogoutRequested", main)
        self.assertIn('root.tr("dialog.logout.title")', main)


if __name__ == "__main__":
    unittest.main()
