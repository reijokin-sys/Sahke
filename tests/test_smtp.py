#!/usr/bin/env python3
# Sähke - mail client for Ubuntu Touch
# Copyright (C) 2026 Reijo Kinnunen
#
# SPDX-License-Identifier: GPL-3.0-or-later
"""End to end test of the sending path (phase 3) over a real socket.

    python3 -m unittest discover -s tests -v

A small SMTP server runs on localhost and speaks just enough of the protocol
(EHLO, AUTH PLAIN/LOGIN, MAIL FROM, RCPT TO, DATA, QUIT). The real
``smtplib`` code path then runs against it, and the message the server
received is compared with what the app meant to send. Nothing here touches the
network outside localhost or the user's account.
"""

import base64
import email
import socketserver
import os
import sys
import threading
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import mail  # noqa: E402  (the path is set up just above)


class _FakeSmtpServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True

    def __init__(self, credentials=("user@example.org", "secret"),
                 accept_auth=True):
        super().__init__(("127.0.0.1", 0), _FakeSmtpHandler)
        self.credentials = credentials
        self.accept_auth = accept_auth
        self.commands = []
        self.message = None


class _FakeSmtpHandler(socketserver.StreamRequestHandler):
    def _reply(self, text):
        self.wfile.write(text.encode("utf-8") + b"\r\n")

    def _auth(self, username, password):
        server = self.server
        if server.accept_auth and (username, password) == server.credentials:
            self._reply("235 2.7.0 Authentication successful")
        else:
            self._reply("535 5.7.8 Authentication credentials invalid")

    def handle(self):
        server = self.server
        self._reply("220 fake ESMTP")
        while True:
            line = self.rfile.readline()
            if not line:
                break
            command = line.decode("utf-8", "replace").strip()
            server.commands.append(command)
            upper = command.upper()
            if upper.startswith(("EHLO", "HELO")):
                self._reply("250-fake")
                self._reply("250-AUTH PLAIN LOGIN")
                self._reply("250 8BITMIME")
            elif upper.startswith("AUTH PLAIN"):
                parts = command.split()
                if len(parts) > 2:
                    raw = base64.b64decode(parts[2]).decode("utf-8")
                    _, username, password = raw.split("\x00")
                    self._auth(username, password)
                else:
                    self._reply("334 ")
                    raw = base64.b64decode(self.rfile.readline().strip()).decode("utf-8")
                    _, username, password = raw.split("\x00")
                    self._auth(username, password)
            elif upper.startswith("AUTH LOGIN"):
                self._reply("334 VXNlcm5hbWU6")
                username = base64.b64decode(self.rfile.readline().strip()).decode()
                self._reply("334 UGFzc3dvcmQ6")
                password = base64.b64decode(self.rfile.readline().strip()).decode()
                self._auth(username, password)
            elif upper.startswith("MAIL FROM"):
                self._reply("250 2.1.0 OK")
            elif upper.startswith("RCPT TO"):
                self._reply("250 2.1.5 OK")
            elif upper.startswith("DATA"):
                self._reply("354 End data with <CR><LF>.<CR><LF>")
                chunk = b""
                while True:
                    row = self.rfile.readline()
                    if row in (b".\r\n", b".\n", b""):
                        break
                    chunk += row
                server.message = chunk
                self._reply("250 2.0.0 OK: queued")
            elif upper.startswith(("RSET", "NOOP")):
                self._reply("250 OK")
            elif upper.startswith("QUIT"):
                self._reply("221 Bye")
                break
            else:
                self._reply("500 5.5.1 Unknown command")


def _start_server(**kwargs):
    server = _FakeSmtpServer(**kwargs)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def _config(server, **overrides):
    config = {
        "host": "mail.example.org",
        "port": 995,
        "security": "ssl",
        "protocol": "pop3",
        "username": "user@example.org",
        "password": "secret",
        "smtp_host": "127.0.0.1",
        "smtp_port": server.server_address[1],
        "smtp_security": "plain",
    }
    config.update(overrides)
    return config


class SendingTests(unittest.TestCase):
    def setUp(self):
        self.server = _start_server()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()

    def test_message_reaches_the_server_with_headers_and_utf8_body(self):
        message = mail.smtp_send(
            _config(self.server),
            "friend@example.org",
            "Tervehdys ääkkösillä",
            "Moi!\n\nTämä on ääkkösiä sisältävä viesti.\n",
        )
        self.assertEqual(message["To"], "friend@example.org")
        self.assertIn("Tervehdys", str(message["Subject"]))

        received = email.message_from_bytes(self.server.message)
        self.assertEqual(received["To"], "friend@example.org")
        self.assertEqual(received["From"], "user@example.org")
        self.assertIn("Tervehdys", str(received["Subject"]))
        self.assertIn("ääkkösiä", received.get_payload(decode=True).decode("utf-8"))
        self.assertTrue(received["Message-ID"])
        self.assertTrue(received["Date"])

    def test_reply_carries_in_reply_to(self):
        mail.smtp_send(
            _config(self.server),
            "friend@example.org",
            "Re: Tervehdys",
            "Kiitos!",
            in_reply_to="<one@example.org>",
            references="<one@example.org>",
        )
        received = email.message_from_bytes(self.server.message)
        self.assertEqual(received["In-Reply-To"], "<one@example.org>")
        self.assertEqual(received["References"], "<one@example.org>")
        self.assertTrue(str(received["Subject"]).startswith("Re:"))

    def test_the_client_only_sends_the_documented_commands(self):
        mail.smtp_send(_config(self.server), "friend@example.org", "Aihe", "Runko")
        allowed = ("EHLO", "AUTH", "MAIL FROM", "RCPT TO", "DATA", "QUIT",
                   "RSET", "NOOP")
        for command in self.server.commands:
            self.assertTrue(
                command.upper().startswith(allowed),
                "unexpected SMTP command: %r" % command,
            )

    def test_missing_recipient_is_an_honest_error(self):
        with self.assertRaises(mail.MailError) as caught:
            mail.smtp_send(_config(self.server), "", "Aihe", "Runko")
        self.assertIn("vastaanottajan", str(caught.exception))
        self.assertIsNone(self.server.message)

    def test_missing_password_is_an_honest_error(self):
        with self.assertRaises(mail.MailError) as caught:
            mail.smtp_send(_config(self.server, password=""),
                           "friend@example.org", "Aihe", "Runko")
        self.assertIn("Salasana", str(caught.exception))

    def test_missing_account_is_an_honest_error(self):
        with self.assertRaises(mail.MailError) as caught:
            mail.smtp_send(_config(self.server, host="", username=""),
                           "friend@example.org", "Aihe", "Runko")
        self.assertIn("Asetukset", str(caught.exception))

    def test_refused_credentials_say_so(self):
        server = _start_server(accept_auth=False)
        try:
            with self.assertRaises(mail.MailError) as caught:
                mail.smtp_send(_config(server), "friend@example.org", "Aihe", "Runko")
            self.assertIn("Kirjautuminen epäonnistui", str(caught.exception))
        finally:
            server.shutdown()
            server.server_close()


class SettingsTests(unittest.TestCase):
    def test_smtp_defaults_follow_the_incoming_server(self):
        config = mail.normalise_config(
            "mail.example.org", 995, "ssl", "user@example.org", "pw"
        )
        self.assertEqual(config["smtp_host"], "mail.example.org")
        self.assertEqual(config["smtp_port"], 465)
        self.assertEqual(config["smtp_security"], "ssl")

    def test_hand_set_smtp_server_survives_a_save(self):
        first = mail.normalise_config("mail.example.org", 995, "ssl", "u@e", "pw")
        first["smtp_host"] = "smtp.example.org"
        first["smtp_port"] = 2525
        second = mail.normalise_config("mail.example.org", 995, "ssl", "u@e", "", first)
        self.assertEqual(second["smtp_host"], "smtp.example.org")
        self.assertEqual(second["smtp_port"], 2525)
        self.assertEqual(second["password"], "pw")

    def test_smtp_fields_from_the_settings_page_are_kept(self):
        config = mail.normalise_config_for(
            "pop3", "mail.example.org", "995", "ssl", "u@e", "pw",
            smtp_host="smtp.example.org", smtp_port="2525",
            smtp_security="starttls")
        self.assertEqual(config["host"], "mail.example.org")
        self.assertEqual(config["smtp_host"], "smtp.example.org")
        self.assertEqual(config["smtp_port"], 2525)
        self.assertEqual(config["smtp_security"], "starttls")

    def test_empty_smtp_host_follows_the_incoming_server(self):
        config = mail.normalise_config(
            "mail.example.org", 995, "ssl", "u@e", "pw", smtp_host="")
        self.assertEqual(config["smtp_host"], "mail.example.org")

    def test_a_hand_set_host_can_be_given_back_to_the_incoming_server(self):
        first = mail.normalise_config(
            "mail.example.org", 995, "ssl", "u@e", "pw",
            smtp_host="smtp.example.org")
        second = mail.normalise_config(
            "mail.example.org", 995, "ssl", "u@e", "", previous=first,
            smtp_host="")
        self.assertEqual(second["smtp_host"], "mail.example.org")

    def test_an_auto_filled_host_keeps_following_the_incoming_server(self):
        first = mail.normalise_config("mail.example.org", 995, "ssl", "u@e", "pw")
        self.assertEqual(first["smtp_host"], "mail.example.org")
        second = mail.normalise_config("mail.other.org", 995, "ssl", "u@e", "",
                                       previous=first)
        self.assertEqual(second["smtp_host"], "mail.other.org")

    def test_empty_smtp_port_follows_the_security(self):
        for security, expected in (("ssl", 465), ("starttls", 587), ("plain", 25)):
            config = mail.normalise_config(
                "mail.example.org", 995, "ssl", "u@e", "pw",
                smtp_security=security, smtp_port="")
            self.assertEqual(config["smtp_port"], expected)
            self.assertEqual(config["smtp_security"], security)

    def test_unknown_sending_security_falls_back_to_ssl(self):
        config = mail.normalise_config(
            "mail.example.org", 995, "ssl", "u@e", "pw",
            smtp_security="smtps", smtp_port="")
        self.assertEqual(config["smtp_security"], "ssl")
        self.assertEqual(config["smtp_port"], 465)

    def test_public_config_never_exposes_the_password(self):
        config = mail.normalise_config("mail.example.org", 995, "ssl", "u@e", "pw")
        visible = mail.public_config(config)
        self.assertNotIn("password", visible)
        self.assertTrue(visible["has_password"])
        self.assertIn("smtp_host", visible)


if __name__ == "__main__":
    unittest.main()
