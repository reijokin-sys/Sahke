#!/usr/bin/env python3
# Sähke - mail client for Ubuntu Touch
# Copyright (C) 2026 Reijo Kinnunen
#
# SPDX-License-Identifier: GPL-3.0-or-later
"""End to end test of the IMAP backend over a real socket.

    python3 -m unittest discover -s tests -v

The other test file feeds the parser response tuples it makes up itself. This
file starts a small IMAP server on localhost, wraps it in TLS with a
certificate generated for the test, and lets the real imaplib code path run:
socket, TLS handshake, greet, LOGIN, EXAMINE and the FETCH responses. That is
what proves the parsing matches what a server actually sends.

Nothing here touches the network outside localhost or the user's account.
"""

import os
import shutil
import socket
import ssl
import subprocess
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import mail  # noqa: E402  (the path is set up just above)


HEADER_FIELDS = (
    b"From: Ada Lovelace <ada@example.org>\r\n"
    b"To: Nobody <nobody@example.org>\r\n"
    b"Subject: =?utf-8?B?VGVzdGkgw6TDtsO2?=\r\n"
    b"Date: Mon, 06 Oct 2026 12:00:00 +0300\r\n"
    b"Message-ID: <one@example.org>\r\n"
    b"\r\n"
)

BODY = (
    b"From: Ada Lovelace <ada@example.org>\r\n"
    b"To: Nobody <nobody@example.org>\r\n"
    b"Subject: =?utf-8?B?VGVzdGkgw6TDtsO2?=\r\n"
    b"Date: Mon, 06 Oct 2026 12:00:00 +0300\r\n"
    b"Message-ID: <one@example.org>\r\n"
    b"MIME-Version: 1.0\r\n"
    b'Content-Type: multipart/alternative; boundary="B"\r\n'
    b"\r\n"
    b"--B\r\n"
    b"Content-Type: text/plain; charset=utf-8\r\n"
    b"\r\n"
    b"Tervehdys listalta.\r\n"
    b"--B\r\n"
    b"Content-Type: text/html; charset=utf-8\r\n"
    b"\r\n"
    b"<p>Tervehdys <b>listalta</b>.</p>\r\n"
    b"--B--\r\n"
)


class FakeImapServer(object):
    """A minimal IMAP server: greeting, LOGIN, EXAMINE, FETCH, LOGOUT."""

    def __init__(self):
        self.requests = []
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(CERT_FILE, KEY_FILE)
        self.context = context
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind(("127.0.0.1", 0))
        self.socket.listen(1)
        self.port = self.socket.getsockname()[1]
        self.thread = threading.Thread(target=self._serve)
        self.thread.daemon = True

    def start(self):
        self.thread.start()
        return self

    def stop(self):
        try:
            self.socket.close()
        except OSError:
            pass

    def _serve(self):
        try:
            raw, _address = self.socket.accept()
        except OSError:
            return
        try:
            connection = self.context.wrap_socket(raw, server_side=True)
        except ssl.SSLError:
            return
        with connection:
            stream = connection.makefile("rwb")
            stream.write(b"* OK [CAPABILITY IMAP4REV1] test server ready\r\n")
            stream.flush()
            while True:
                line = stream.readline()
                if not line:
                    break
                text = line.decode("utf-8", "replace").rstrip("\r\n")
                tag, _, command = text.partition(" ")
                self.requests.append(command.upper())
                upper = command.upper()
                if upper.startswith("CAPABILITY"):
                    stream.write(b"* CAPABILITY IMAP4REV1\r\n")
                    stream.write(b"%s OK CAPABILITY done\r\n" % tag.encode())
                elif upper.startswith("LOGIN"):
                    if "wrong" in command:
                        stream.write(b"%s NO [AUTHENTICATIONFAILED] nope\r\n"
                                     % tag.encode())
                    else:
                        stream.write(b"%s OK LOGIN done\r\n" % tag.encode())
                elif upper.startswith("EXAMINE"):
                    stream.write(b"* 1 EXISTS\r\n")
                    stream.write(b"* FLAGS (\\Seen \\Answered)\r\n")
                    stream.write(b"%s OK [READ-ONLY] EXAMINE done\r\n"
                                 % tag.encode())
                elif upper.startswith("SELECT"):
                    stream.write(b"* 1 EXISTS\r\n")
                    stream.write(b"%s OK [READ-WRITE] SELECT done\r\n"
                                 % tag.encode())
                elif upper.startswith("FETCH"):
                    stream.write(
                        b"* 1 FETCH (UID 7 FLAGS (\\Seen) RFC822.SIZE %d "
                        b"BODY[HEADER.FIELDS (FROM TO SUBJECT DATE MESSAGE-ID)] "
                        b"{%d}\r\n"
                        % (len(BODY), len(HEADER_FIELDS))
                    )
                    stream.write(HEADER_FIELDS)
                    stream.write(b")\r\n")
                    stream.write(b"%s OK FETCH done\r\n" % tag.encode())
                elif upper.startswith("UID FETCH"):
                    stream.write(b"* 1 FETCH (UID 7 BODY[] {%d}\r\n" % len(BODY))
                    stream.write(BODY)
                    stream.write(b")\r\n")
                    stream.write(b"%s OK UID FETCH done\r\n" % tag.encode())
                elif upper.startswith("CLOSE"):
                    stream.write(b"%s OK CLOSE done\r\n" % tag.encode())
                elif upper.startswith("LOGOUT"):
                    stream.write(b"* BYE bye\r\n")
                    stream.write(b"%s OK LOGOUT done\r\n" % tag.encode())
                    stream.flush()
                    break
                else:
                    stream.write(b"%s OK done\r\n" % tag.encode())
                stream.flush()


CERT_DIR = None
CERT_FILE = None
KEY_FILE = None


def setUpModule():
    global CERT_DIR, CERT_FILE, KEY_FILE
    CERT_DIR = tempfile.mkdtemp(prefix="sahkoposti-tls-")
    CERT_FILE = os.path.join(CERT_DIR, "cert.pem")
    KEY_FILE = os.path.join(CERT_DIR, "key.pem")
    subprocess.check_call(
        [
            "openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
            "-keyout", KEY_FILE, "-out", CERT_FILE, "-days", "1",
            "-subj", "/CN=localhost",
            "-addext", "subjectAltName=DNS:localhost,IP:127.0.0.1",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def tearDownModule():
    if CERT_DIR:
        shutil.rmtree(CERT_DIR, ignore_errors=True)


def test_context():
    context = ssl.create_default_context(cafile=CERT_FILE)
    context.check_hostname = False
    return context


class SocketTests(unittest.TestCase):
    def setUp(self):
        self.language_directory = tempfile.mkdtemp(prefix="sahkoposti-language-")
        self.previous_data_dir = os.environ.get("SAHKOPOSTI_DATA_DIR")
        os.environ["SAHKOPOSTI_DATA_DIR"] = self.language_directory
        mail.set_language("en")
        self.server = FakeImapServer().start()
        self.config = {
            "host": "127.0.0.1",
            "port": self.server.port,
            "security": "ssl",
            "username": "ada",
            "password": "secret",
        }

    def tearDown(self):
        self.server.stop()
        if self.previous_data_dir is None:
            os.environ.pop("SAHKOPOSTI_DATA_DIR", None)
        else:
            os.environ["SAHKOPOSTI_DATA_DIR"] = self.previous_data_dir
        shutil.rmtree(self.language_directory, ignore_errors=True)

    def factory(self, config):
        # The factory must honour the config it is handed; otherwise the
        # wrong-password and unreachable-port cases would silently test the
        # good settings again.
        return mail.ImapClient(config, timeout=15, ssl_context=test_context())

    def test_inbox_list_over_a_real_socket(self):
        messages = mail.imap_inbox_list(
            self.config, 50, client_factory=self.factory
        )
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["uid"], 7)
        self.assertEqual(messages[0]["subject"], "Testi äöö")
        self.assertEqual(messages[0]["from"], "Ada Lovelace <ada@example.org>")
        self.assertTrue(messages[0]["seen"])
        self.assertEqual(messages[0]["size"], len(BODY))
        # The mailbox must have been opened read only.
        self.assertTrue(
            any(request.startswith("EXAMINE") for request in self.server.requests),
            self.server.requests,
        )
        self.assertFalse(
            any(request.startswith("SELECT") for request in self.server.requests),
            self.server.requests,
        )

    def test_message_over_a_real_socket(self):
        message = mail.imap_fetch_message(
            self.config, 7, client_factory=self.factory
        )
        self.assertEqual(message["uid"], 7)
        self.assertEqual(message["subject"], "Testi äöö")
        self.assertEqual(message["text"], "Tervehdys listalta.")

    def test_wrong_password_over_a_real_socket(self):
        config = dict(self.config, password="wrong-on-purpose")
        with self.assertRaises(mail.MailError) as caught:
            mail.imap_inbox_list(config, 5, client_factory=self.factory)
        self.assertIn("Login failed", str(caught.exception))

    def test_unreachable_port_is_reported_cleanly(self):
        config = dict(self.config, port=1)
        with self.assertRaises(mail.MailError) as caught:
            mail.imap_inbox_list(config, 5, client_factory=self.factory)
        self.assertIn("Connection to", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
