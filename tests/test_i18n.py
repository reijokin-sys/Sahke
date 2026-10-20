#!/usr/bin/env python3
# Sähke - mail client for Ubuntu Touch
# Copyright (C) 2026 Reijo Kinnunen
#
# SPDX-License-Identifier: GPL-3.0-or-later
"""Language selection and backend error translation."""

import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import mail  # noqa: E402  (path is set up just above)


class LanguageTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.mkdtemp(prefix="sahke-i18n-")
        self.old_data_dir = os.environ.get("SAHKOPOSTI_DATA_DIR")
        os.environ["SAHKOPOSTI_DATA_DIR"] = self.directory

    def tearDown(self):
        if self.old_data_dir is None:
            os.environ.pop("SAHKOPOSTI_DATA_DIR", None)
        else:
            os.environ["SAHKOPOSTI_DATA_DIR"] = self.old_data_dir
        shutil.rmtree(self.directory, ignore_errors=True)

    def test_default_language_is_english(self):
        self.assertEqual(mail.language(), {"ok": True, "result": "en"})

    def test_language_choice_is_written_and_read_back(self):
        self.assertEqual(mail.set_language("fi"), {"ok": True, "result": "fi"})
        self.assertEqual(mail.language(), {"ok": True, "result": "fi"})

    def test_invalid_language_does_not_change_the_choice(self):
        mail.set_language("fi")
        result = mail.set_language("sv")
        self.assertFalse(result["ok"])
        self.assertEqual(mail.language()["result"], "fi")

    def test_backend_error_uses_english_by_default(self):
        with self.assertRaises(mail.MailError) as caught:
            mail.SmtpClient({}).connect()
        self.assertIn("sending server is not configured", str(caught.exception))

    def test_backend_error_uses_finnish_after_selection(self):
        mail.set_language("fi")
        with self.assertRaises(mail.MailError) as caught:
            mail.SmtpClient({}).connect()
        self.assertIn("Lähettävää palvelinta ei ole asetettu", str(caught.exception))

    def test_login_error_includes_server_text_in_selected_language(self):
        mail.set_language("en")
        text = mail.login_failed_message(Exception("bad password"))
        self.assertIn("Login failed", text)
        self.assertIn("Server said: bad password", text)

        mail.set_language("fi")
        text = mail.login_failed_message(Exception("bad password"))
        self.assertIn("Kirjautuminen epäonnistui", text)
        self.assertIn("Palvelin sanoi: bad password", text)

    def test_send_validation_error_is_localized(self):
        config = {"host": "mail.example.org", "username": "user@example.org",
                  "password": "secret"}
        with self.assertRaises(mail.MailError) as caught:
            mail.smtp_send(config, "", "Subject", "Body")
        self.assertIn("recipient", str(caught.exception).lower())

        mail.set_language("fi")
        with self.assertRaises(mail.MailError) as caught:
            mail.smtp_send(config, "", "Subject", "Body")
        self.assertIn("vastaanottajan", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
