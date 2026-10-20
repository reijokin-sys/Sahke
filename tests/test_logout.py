#!/usr/bin/env python3
# Sähke - mail client for Ubuntu Touch
# Copyright (C) 2026 Reijo Kinnunen
#
# SPDX-License-Identifier: GPL-3.0-or-later
"""Signing out removes the local account and trash, not the UI preferences."""

import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import mail  # noqa: E402


class LogoutTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.mkdtemp(prefix="sahke-logout-")
        self.previous = os.environ.get("SAHKOPOSTI_DATA_DIR")
        os.environ["SAHKOPOSTI_DATA_DIR"] = self.directory
        self.old_forget = mail.credentials.forget
        self.forgotten = []
        mail.credentials.forget = self.forget

    def tearDown(self):
        mail.credentials.forget = self.old_forget
        if self.previous is None:
            os.environ.pop("SAHKOPOSTI_DATA_DIR", None)
        else:
            os.environ["SAHKOPOSTI_DATA_DIR"] = self.previous
        shutil.rmtree(self.directory, ignore_errors=True)

    def forget(self, username):
        self.forgotten.append(username)
        return True

    def test_logout_removes_account_and_trash_but_keeps_language(self):
        config = mail.normalise_config(
            "mail.example.org", "993", "ssl", "user@example.org", "secret"
        )
        mail.save_config_dict(config)
        mail.save_trash([
            {"uid": "7", "from": "Ada <ada@example.org>",
             "subject": "Test", "date": "2026-10-20T10:00:00+00:00",
             "size": 100, "seen": False}
        ])
        mail.set_language("fi")

        backend = mail.Mail()
        result = backend.logout()

        self.assertTrue(result["ok"])
        self.assertFalse(os.path.exists(mail.config_path()))
        self.assertFalse(os.path.exists(mail.trash_path()))
        self.assertEqual(mail.language()["result"], "fi")
        self.assertEqual(self.forgotten, ["user@example.org"])
        self.assertEqual(backend.config, {})

    def test_logout_is_idempotent_without_an_account(self):
        backend = mail.Mail()
        result = backend.logout()
        self.assertTrue(result["ok"])
        self.assertEqual(self.forgotten, [])


if __name__ == "__main__":
    unittest.main()
