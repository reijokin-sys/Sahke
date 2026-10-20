#!/usr/bin/env python3
# Sähke - mail client for Ubuntu Touch
# Copyright (C) 2026 Reijo Kinnunen
#
# SPDX-License-Identifier: GPL-3.0-or-later
"""Unit tests for mail.py. Run from the project root:

    python3 -m unittest discover -s tests -v

The tests use a fake IMAP connection, so they need neither a network nor a
real account.
"""

import email
import imaplib
import json
import os
import shutil
import stat
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import mail  # noqa: E402  (path is set up just above)


def build_message(headers, body, subtype="plain", charset="utf-8"):
    if charset == "utf-8":
        encoded = body.encode("utf-8")
        transfer = "8bit"
    else:
        encoded = body.encode(charset)
        transfer = "8bit"
    head = "".join("%s: %s\r\n" % (key, value) for key, value in headers.items())
    return (
        ("%sContent-Type: text/%s; charset=%s\r\n"
         "Content-Transfer-Encoding: %s\r\n\r\n" % (head, subtype, charset, transfer))
        .encode("utf-8")
        + encoded
    )


class RecordingPyOtherSide(object):
    def __init__(self):
        self.signals = []

    def send(self, name, *args):
        self.signals.append((name, args))

    def only(self, name):
        return [args for signal, args in self.signals if signal == name]


class FakeConnection(object):
    """Stands in for imaplib.IMAP4_SSL in the tests."""

    def __init__(self, total=0, fetch_data=None, uid_data=None):
        self.total = total
        self.fetch_data = fetch_data or []
        self.uid_data = uid_data or []
        self.selected = None
        self.logged_out = False

    def select(self, mailbox, readonly=False):
        self.selected = (mailbox, readonly)
        return ("OK", [str(self.total).encode()])

    def fetch(self, spec, query):
        return ("OK", self.fetch_data)

    def uid(self, command, uid, query):
        return ("OK", self.uid_data)

    def logout(self):
        self.logged_out = True


class FakeClient(object):
    def __init__(self, connection=None, error=None):
        self.connection = connection or FakeConnection()
        self.error = error
        self.closed = False

    def connect(self):
        if self.error is not None:
            raise self.error
        return self.connection

    def close(self, connection):
        self.closed = True
        connection.logout()


def header_response(uid, flags, header_bytes, size=1234):
    meta = (
        b'%d (UID %d FLAGS (%s) RFC822.SIZE %d '
        b'BODY[HEADER.FIELDS (FROM TO SUBJECT DATE MESSAGE-ID)] {%d}'
        % (uid, uid, flags, size, len(header_bytes))
    )
    return [(meta, header_bytes), b")"]


class HeaderDecodingTests(unittest.TestCase):
    def test_rfc2047_subject_is_decoded(self):
        raw = "=?utf-8?B?VGVzdGkgw6TDtsO2?="
        self.assertEqual(mail.decode_header_value(raw), "Testi äöö")

    def test_broken_rfc2047_header_is_shown_as_it_is(self):
        raw = "=?utf-8?B?VGVzdGkgw6TDw7bDtg==?="
        self.assertEqual(mail.decode_header_value(raw), raw)

    def test_plain_subject_is_untouched(self):
        self.assertEqual(mail.decode_header_value("Hello there"), "Hello there")

    def test_none_becomes_empty_string(self):
        self.assertEqual(mail.decode_header_value(None), "")

    def test_address_with_name(self):
        self.assertEqual(
            mail.format_address("Ada Lovelace <ada@example.org>"),
            "Ada Lovelace <ada@example.org>",
        )

    def test_address_without_name(self):
        self.assertEqual(mail.format_address("ada@example.org"), "ada@example.org")

    def test_date_becomes_iso(self):
        value = mail.format_date("Mon, 06 Oct 2026 12:00:00 +0300")
        self.assertTrue(value.startswith("2026-10-06T12:00:00"))

    def test_unparsable_date_is_empty(self):
        self.assertEqual(mail.format_date("not a date"), "")


class HtmlTests(unittest.TestCase):
    def test_tags_are_stripped(self):
        self.assertEqual(
            mail.html_to_text("<p>Hello <b>there</b></p>"), "Hello there"
        )

    def test_blocks_become_line_breaks(self):
        text = mail.html_to_text("<p>One</p><p>Two</p>")
        self.assertEqual(text, "One\n\nTwo")

    def test_many_list_items_do_not_blow_up(self):
        text = mail.html_to_text("<ul><li>a</li><li>b</li></ul>")
        self.assertEqual(text, "a\n\nb")

    def test_script_and_style_are_dropped(self):
        text = mail.html_to_text(
            "<style>p{color:red}</style><p>Visible</p><script>x=1</script>"
        )
        self.assertEqual(text, "Visible")

    def test_entities_are_decoded(self):
        self.assertEqual(mail.html_to_text("<p>a &amp; b</p>"), "a & b")

    def test_br_becomes_newline(self):
        self.assertEqual(mail.html_to_text("one<br>two"), "one\ntwo")


class BodyTests(unittest.TestCase):
    def test_plain_body_is_used(self):
        raw = build_message({"Subject": "Hi"}, "Plain body")
        self.assertEqual(mail.message_text(email.message_from_bytes(raw)), "Plain body")

    def test_html_only_body_is_stripped(self):
        raw = build_message({"Subject": "Hi"}, "<p>Hello <b>HTML</b></p>", "html")
        self.assertEqual(mail.message_text(email.message_from_bytes(raw)), "Hello HTML")

    def test_plain_is_preferred_over_html(self):
        raw = (
            b"Subject: Both\r\n"
            b'Content-Type: multipart/alternative; boundary="B"\r\n\r\n'
            b"--B\r\nContent-Type: text/plain; charset=utf-8\r\n\r\n"
            b"the plain one\r\n"
            b"--B\r\nContent-Type: text/html; charset=utf-8\r\n\r\n"
            b"<p>the html one</p>\r\n"
            b"--B--\r\n"
        )
        self.assertEqual(mail.message_text(email.message_from_bytes(raw)), "the plain one")

    def test_non_utf8_charset_is_decoded(self):
        raw = build_message(
            {"Subject": "Latin"}, "Hyv\u00e4\u00e4 p\u00e4iv\u00e4\u00e4",
            charset="iso-8859-1",
        )
        self.assertEqual(
            mail.message_text(email.message_from_bytes(raw)), "Hyv\u00e4\u00e4 p\u00e4iv\u00e4\u00e4"
        )

    def test_attachment_is_not_part_of_the_body(self):
        raw = (
            b"Subject: With attachment\r\n"
            b'Content-Type: multipart/mixed; boundary="B"\r\n\r\n'
            b"--B\r\nContent-Type: text/plain; charset=utf-8\r\n\r\n"
            b"see the file\r\n"
            b"--B\r\nContent-Type: text/plain; charset=utf-8\r\n"
            b'Content-Disposition: attachment; filename="notes.txt"\r\n\r\n'
            b"attached text\r\n"
            b"--B--\r\n"
        )
        message = email.message_from_bytes(raw)
        self.assertEqual(mail.message_text(message), "see the file")
        self.assertEqual(mail._attachment_names(message), ["notes.txt"])

    def test_empty_body_gives_empty_string(self):
        raw = build_message({"Subject": "Nothing"}, "")
        self.assertEqual(mail.message_text(email.message_from_bytes(raw)), "")

    def test_snippet_is_collapsed_and_cut(self):
        snippet = mail.message_snippet("a" * 10 + "\n\n" + "b" * 200, length=20)
        self.assertTrue(len(snippet) <= 20)
        self.assertTrue(snippet.endswith("\u2026"))


class FetchParsingTests(unittest.TestCase):
    def test_headers_are_parsed_and_sorted_newest_first(self):
        first = b"From: Ada <ada@example.org>\r\nSubject: Older\r\n\r\n"
        second = b"From: Bob <bob@example.org>\r\nSubject: Newer\r\n\r\n"
        responses = header_response(1, b"\\Seen", first)
        responses += header_response(2, b"", second)
        messages = mail.parse_fetch_headers(responses)
        self.assertEqual([message["uid"] for message in messages], [2, 1])
        self.assertEqual(messages[1]["subject"], "Older")
        self.assertTrue(messages[1]["seen"])
        self.assertFalse(messages[0]["seen"])
        self.assertEqual(messages[0]["size"], 1234)

    def test_junk_entries_are_ignored(self):
        self.assertEqual(mail.parse_fetch_headers([b")", None, (b"x",)]), [])


class InboxListTests(unittest.TestCase):
    def setUp(self):
        self.language_directory = tempfile.mkdtemp(prefix="sahkoposti-language-")
        self.previous_data_dir = os.environ.get("SAHKOPOSTI_DATA_DIR")
        os.environ["SAHKOPOSTI_DATA_DIR"] = self.language_directory
        mail.set_language("en")

    def tearDown(self):
        if self.previous_data_dir is None:
            os.environ.pop("SAHKOPOSTI_DATA_DIR", None)
        else:
            os.environ["SAHKOPOSTI_DATA_DIR"] = self.previous_data_dir
        shutil.rmtree(self.language_directory, ignore_errors=True)

    def test_server_text_is_shown_for_a_failed_login(self):
        error = imaplib.IMAP4.error(
            b"[AUTHENTICATIONFAILED] Authentication failed."
        )
        message = mail.login_failed_message(error)
        self.assertIn("Login failed. Check the username and password.",
                      message)
        self.assertIn("[AUTHENTICATIONFAILED]", message)
        self.assertNotIn("b'", message)

    def test_a_silent_server_keeps_the_short_message(self):
        self.assertEqual(
            mail.login_failed_message(imaplib.IMAP4.error()),
            "Login failed. Check the username and password.",
        )

    def test_empty_mailbox_returns_no_messages(self):
        client = FakeClient(FakeConnection(total=0))
        self.assertEqual(
            mail.imap_inbox_list({"host": "imap.example.org"}, 50,
                                 client_factory=lambda config: client),
            [],
        )

    def test_inbox_is_opened_read_only(self):
        connection = FakeConnection(total=0)
        client = FakeClient(connection)
        mail.imap_inbox_list({}, 10, client_factory=lambda config: client)
        self.assertEqual(connection.selected, ("INBOX", True))
        self.assertTrue(connection.logged_out)

    def test_missing_server_is_reported(self):
        with self.assertRaises(mail.MailError):
            mail.ImapClient({}).connect()

    def test_login_error_is_reported(self):
        client = FakeClient(error=mail.MailError("Login failed. Check the username and password."))
        with self.assertRaises(mail.MailError) as caught:
            mail.imap_inbox_list({}, 10, client_factory=lambda config: client)
        self.assertIn("Login failed", str(caught.exception))

    def test_list_limit_is_clamped(self):
        connection = FakeConnection(total=0)
        client = FakeClient(connection)
        mail.imap_inbox_list({}, 100000, client_factory=lambda config: client)
        self.assertTrue(client.closed)


class FetchMessageTests(unittest.TestCase):
    def test_message_body_is_fetched_and_never_marked_seen(self):
        raw = build_message({"From": "Ada <ada@example.org>", "Subject": "Hi"},
                            "Body text")
        connection = FakeConnection(total=1, uid_data=[(b"1 (UID 5 BODY[]", raw)])
        client = FakeClient(connection)
        result = mail.imap_fetch_message({}, 5, client_factory=lambda config: client)
        self.assertEqual(result["uid"], 5)
        self.assertEqual(result["subject"], "Hi")
        self.assertEqual(result["text"], "Body text")
        self.assertEqual(connection.selected, ("INBOX", True))

    def test_missing_message_is_reported(self):
        connection = FakeConnection(total=1, uid_data=[b")"])
        client = FakeClient(connection)
        with self.assertRaises(mail.MailError):
            mail.imap_fetch_message({}, 5, client_factory=lambda config: client)


class SettingsTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.mkdtemp(prefix="sahkoposti-test-")
        self.previous = os.environ.get("SAHKOPOSTI_DATA_DIR")
        os.environ["SAHKOPOSTI_DATA_DIR"] = self.directory
        # The keyring is whatever this machine happens to have; the tests must
        # not depend on it (nor write into it). One test turns it on with a
        # stand-in of its own.
        self.keyring_before = mail.credentials.available
        mail.credentials.available = lambda: False

    def tearDown(self):
        mail.credentials.available = self.keyring_before
        if self.previous is None:
            os.environ.pop("SAHKOPOSTI_DATA_DIR", None)
        else:
            os.environ["SAHKOPOSTI_DATA_DIR"] = self.previous
        shutil.rmtree(self.directory, ignore_errors=True)

    def test_missing_config_is_empty(self):
        self.assertEqual(mail.load_config_dict(), {})

    def test_settings_are_saved_with_0600(self):
        config = mail.normalise_config("imap.example.org", "993", "ssl", "ada",
                                       "secret")
        path = mail.save_config_dict(config)
        mode = stat.S_IMODE(os.stat(path).st_mode)
        self.assertEqual(mode, 0o600)
        self.assertEqual(mail.load_config_dict()["host"], "imap.example.org")

    def test_public_config_hides_the_password(self):
        config = mail.normalise_config("imap.example.org", 993, "ssl", "ada",
                                       "secret")
        visible = mail.public_config(config)
        self.assertNotIn("password", visible)
        self.assertTrue(visible["has_password"])
        self.assertTrue(visible["configured"])

    def test_empty_password_keeps_the_old_one(self):
        previous = mail.normalise_config("imap.example.org", 993, "ssl", "ada",
                                         "secret")
        config = mail.normalise_config("imap.example.org", 993, "ssl", "ada", "",
                                       previous=previous)
        self.assertEqual(config["password"], "secret")

    def test_without_a_keyring_the_password_stays_in_the_file(self):
        # The fallback that keeps the app working: on a machine with no
        # session bus (and in these tests) nothing may be lost.
        self.assertFalse(mail.credentials.available())
        config = mail.normalise_config("imap.example.org", 993, "ssl", "ada",
                                       "secret")
        mail.save_config_dict(config)
        saved = mail.load_config_dict()
        self.assertEqual(saved["password"], "secret")
        self.assertFalse(saved["password_in_keyring"])
        self.assertEqual(mail.public_config(saved)["password_location"], "file")

    def test_a_working_keyring_keeps_the_password_out_of_the_file(self):
        tallennettu = {}
        alkuperaiset = (mail.credentials.available, mail.credentials.store,
                        mail.credentials.lookup)
        mail.credentials.available = lambda: True
        mail.credentials.store = lambda user, pw: tallennettu.setdefault(user, pw) and True
        mail.credentials.lookup = lambda user: tallennettu.get(user)
        try:
            config = mail.normalise_config("imap.example.org", 993, "ssl",
                                           "ada", "secret")
            mail.save_config_dict(config)
            with open(mail.config_path(), encoding="utf-8") as handle:
                on_disk = json.load(handle)
            self.assertNotIn("password", on_disk)
            self.assertTrue(on_disk["password_in_keyring"])
            self.assertEqual(tallennettu["ada"], "secret")
            # And it is read back from there.
            self.assertEqual(mail.load_config_dict()["password"], "secret")
            self.assertEqual(mail.public_config(
                mail.load_config_dict())["password_location"], "keyring")
        finally:
            (mail.credentials.available, mail.credentials.store,
             mail.credentials.lookup) = alkuperaiset

    def test_the_visible_settings_say_where_the_password_is(self):
        config = mail.normalise_config("imap.example.org", 993, "ssl", "ada",
                                       "secret")
        self.assertEqual(mail.public_config(config)["password_location"], "file")
        config.pop("password")
        config["password_in_keyring"] = True
        visible = mail.public_config(config)
        self.assertEqual(visible["password_location"], "keyring")
        self.assertNotIn("password", visible)
        self.assertNotIn("password_in_keyring", visible)

    def test_default_ports_follow_the_security_choice(self):
        self.assertEqual(
            mail.normalise_config("h", "", "starttls", "u", "p")["port"], 143
        )
        self.assertEqual(
            mail.normalise_config("h", "", "ssl", "u", "p")["port"], 993
        )

    def test_the_settings_page_can_set_the_sending_server(self):
        # The exact call the settings page makes through Main.saveSettings.
        result = mail.configure("mail.example.org", "995", "ssl", "ada",
                                "secret", "pop3", "smtp.example.org", "2525",
                                "starttls")
        self.assertTrue(result["ok"])
        saved = mail.load_config_dict()
        self.assertEqual(saved["smtp_host"], "smtp.example.org")
        self.assertEqual(saved["smtp_port"], 2525)
        self.assertEqual(saved["smtp_security"], "starttls")
        # An empty sending host follows the incoming server again, and the
        # port follows the security.
        result = mail.configure("mail.other.org", "995", "ssl", "ada", "",
                                "pop3", "", "", "ssl")
        self.assertTrue(result["ok"])
        saved = mail.load_config_dict()
        self.assertEqual(saved["host"], "mail.other.org")
        self.assertEqual(saved["smtp_host"], "mail.other.org")
        self.assertEqual(saved["smtp_port"], 465)
        self.assertEqual(saved["smtp_security"], "ssl")
        self.assertEqual(saved["password"], "secret")

    def test_broken_config_file_is_ignored(self):
        os.makedirs(self.directory, exist_ok=True)
        with open(mail.config_path(), "w", encoding="utf-8") as handle:
            handle.write("{ not json")
        self.assertEqual(mail.load_config_dict(), {})

    def test_protocol_defaults_to_imap(self):
        self.assertEqual(mail.config_protocol({}), "imap")
        self.assertEqual(mail.config_protocol({"protocol": "nonsense"}), "imap")
        self.assertEqual(mail.config_protocol({"protocol": "POP3"}), "pop3")

    def test_pop3_gets_the_pop3_port(self):
        config = mail.normalise_config_for("pop3", "mail.example.org", "",
                                           "ssl", "ada", "secret")
        self.assertEqual(config["protocol"], "pop3")
        self.assertEqual(config["port"], 995)

    def test_starttls_keeps_the_protocol_default(self):
        config = mail.normalise_config_for("pop3", "mail.example.org", "",
                                           "starttls", "ada", "secret")
        self.assertEqual(config["port"], 110)

    def test_a_typed_port_is_kept(self):
        config = mail.normalise_config_for("pop3", "mail.example.org", "996",
                                           "ssl", "ada", "secret")
        self.assertEqual(config["port"], 996)


class FakePop3Connection(object):
    """A POP3 connection that refuses to delete anything."""

    def __init__(self, messages, uids, allow_delete=False):
        self.messages = messages
        self.uids = uids
        # The reading paths must never delete; only the empty-trash path may,
        # and even then only on purpose.
        self.allow_delete = allow_delete
        self.deleted = []
        self.quit_called = False
        self.closed_without_quit = False

    def uidl(self, which=None):
        lines = [
            ("%d %s" % (index + 1, uid)).encode()
            for index, uid in enumerate(self.uids)
        ]
        return (b"+OK", lines, 0)

    def list(self, which=None):
        lines = [
            ("%d %d" % (index + 1, len(raw))).encode()
            for index, raw in enumerate(self.messages)
        ]
        return (b"+OK", lines, 0)

    def top(self, which, howmuch):
        header = self.messages[which - 1].split(b"\r\n\r\n", 1)[0]
        return (b"+OK", header.split(b"\r\n") + [b""], 0)

    def retr(self, which):
        return (b"+OK", self.messages[which - 1].split(b"\r\n"), 0)

    def dele(self, which):
        if not self.allow_delete:
            raise AssertionError("DELE must never be sent")
        self.deleted.append(which)

    def quit(self):
        self.quit_called = True

    def close(self):
        """Poplib's close: drop the session without QUIT (no commit)."""
        self.closed_without_quit = True


class FakePop3Client(object):
    def __init__(self, connection):
        self.connection = connection
        self.closed = False

    def connect(self):
        return self.connection

    def close(self, connection):
        self.closed = True
        connection.quit()


class Pop3Tests(unittest.TestCase):
    def setUp(self):
        self.messages = [
            build_message({"From": "Ada <ada@example.org>", "Subject": "Older"},
                          "first body"),
            build_message({"From": "Bob <bob@example.org>", "Subject": "Newer"},
                          "second body"),
        ]
        self.connection = FakePop3Connection(self.messages, ["uid-1", "uid-2"])
        self.client = FakePop3Client(self.connection)
        self.config = {"protocol": "pop3", "host": "mail.example.org"}

    def factory(self, config):
        return self.client

    def test_uidl_and_list_are_parsed(self):
        self.assertEqual(
            mail.parse_uidl([b"1 uid-1", b"2 uid-2", b"junk"]),
            {1: "uid-1", 2: "uid-2"},
        )
        self.assertEqual(
            mail.parse_list_sizes([b"1 100", b"2 200"]), {1: 100, 2: 200}
        )

    def test_list_is_newest_first_and_has_no_read_state(self):
        messages = mail.pop3_inbox_list(self.config, 10, client_factory=self.factory)
        self.assertEqual([message["uid"] for message in messages],
                         ["uid-2", "uid-1"])
        self.assertEqual(messages[0]["subject"], "Newer")
        self.assertIsNone(messages[0]["seen"])
        self.assertEqual(messages[0]["size"], len(self.messages[1]))

    def test_message_is_fetched_by_uid(self):
        message = mail.pop3_fetch_message(self.config, "uid-2",
                                          client_factory=self.factory)
        self.assertEqual(message["subject"], "Newer")
        self.assertEqual(message["text"], "second body")

    def test_nothing_is_deleted_and_the_session_is_quit(self):
        mail.pop3_inbox_list(self.config, 10, client_factory=self.factory)
        mail.pop3_fetch_message(self.config, "uid-1", client_factory=self.factory)
        self.assertTrue(self.connection.quit_called)
        self.assertTrue(self.client.closed)

    def test_a_missing_message_is_reported(self):
        with self.assertRaises(mail.MailError):
            mail.pop3_fetch_message(self.config, "uid-404",
                                    client_factory=self.factory)

    def test_empty_mailbox(self):
        empty = FakePop3Client(FakePop3Connection([], []))
        self.assertEqual(
            mail.pop3_inbox_list(self.config, 10,
                                 client_factory=lambda config: empty),
            [],
        )

    def test_backend_picks_pop3_from_the_settings(self):
        backend = mail.Mail(config=self.config)
        recorder = RecordingPyOtherSide()
        previous_pyotherside = mail.pyotherside
        previous_loader = mail.load_config_dict
        previous_pop3 = mail.pop3_inbox_list
        mail.pyotherside = recorder
        mail.load_config_dict = lambda: self.config
        mail.pop3_inbox_list = lambda config, limit: [{"uid": "uid-2"}]
        try:
            result = backend.list_inbox(10)
        finally:
            mail.pyotherside = previous_pyotherside
            mail.load_config_dict = previous_loader
            mail.pop3_inbox_list = previous_pop3
        self.assertTrue(result["ok"])
        self.assertEqual(recorder.only("messageList"), [([{"uid": "uid-2"}],)])


class TrashTests(unittest.TestCase):
    """Delete means "into this app's trash" - the mailbox is never touched."""

    def setUp(self):
        self.directory = tempfile.mkdtemp(prefix="sahkoposti-trash-")
        self.previous = os.environ.get("SAHKOPOSTI_DATA_DIR")
        os.environ["SAHKOPOSTI_DATA_DIR"] = self.directory
        self.messages = [
            build_message({"From": "Ada <ada@example.org>", "Subject": "Older"},
                          "first body"),
            build_message({"From": "Bob <bob@example.org>", "Subject": "Newer"},
                          "second body"),
        ]
        self.connection = FakePop3Connection(self.messages, ["uid-1", "uid-2"])
        self.client = FakePop3Client(self.connection)
        self.config = {"protocol": "pop3", "host": "mail.example.org"}

    def tearDown(self):
        if self.previous is None:
            os.environ.pop("SAHKOPOSTI_DATA_DIR", None)
        else:
            os.environ["SAHKOPOSTI_DATA_DIR"] = self.previous
        shutil.rmtree(self.directory, ignore_errors=True)

    def listing(self):
        return mail.pop3_inbox_list(self.config, 10,
                                    client_factory=lambda config: self.client)

    def test_a_deleted_message_leaves_the_inbox_list(self):
        self.assertEqual([m["uid"] for m in self.listing()], ["uid-2", "uid-1"])
        entry = self.listing()[0]
        mail.move_to_trash(entry)
        self.assertEqual([m["uid"] for m in self.listing()], ["uid-1"])

    def test_the_trash_keeps_what_the_list_needs(self):
        entry = self.listing()[0]
        mail.move_to_trash(entry)
        trash = mail.load_trash()
        self.assertEqual(len(trash), 1)
        self.assertEqual(trash[0]["uid"], "uid-2")
        self.assertEqual(trash[0]["subject"], "Newer")
        self.assertEqual(trash[0]["from"], "Bob <bob@example.org>")
        self.assertIn("deleted", trash[0])
        self.assertEqual(mail.trash_uids(), {"uid-2"})

    def test_the_trash_file_is_private(self):
        mail.move_to_trash(self.listing()[0])
        mode = stat.S_IMODE(os.stat(mail.trash_path()).st_mode)
        self.assertEqual(mode, 0o600)

    def test_deleting_twice_keeps_one_entry(self):
        entry = self.listing()[0]
        mail.move_to_trash(entry)
        mail.move_to_trash(entry)
        self.assertEqual(len(mail.load_trash()), 1)

    def test_a_restored_message_comes_back_to_the_list(self):
        mail.move_to_trash(self.listing()[0])
        self.assertEqual([m["uid"] for m in self.listing()], ["uid-1"])
        mail.restore_from_trash("uid-2")
        self.assertEqual([m["uid"] for m in self.listing()], ["uid-2", "uid-1"])
        self.assertEqual(mail.load_trash(), [])

    def test_deleting_never_opens_the_mailbox(self):
        # The whole point: no connection, no DELE, nothing on the server.
        entry = {"uid": "uid-2", "subject": "Newer"}
        result = mail.delete_message(entry)
        self.assertTrue(result["ok"])
        self.assertFalse(self.connection.quit_called)
        self.assertFalse(self.client.closed)
        self.assertEqual(mail.trash_uids(), {"uid-2"})

    def test_a_broken_trash_file_means_an_empty_trash(self):
        os.makedirs(self.directory, exist_ok=True)
        with open(mail.trash_path(), "w", encoding="utf-8") as handle:
            handle.write("{ not json")
        self.assertEqual(mail.load_trash(), [])
        self.assertEqual(mail.trash_uids(), set())
        self.assertEqual([m["uid"] for m in self.listing()], ["uid-2", "uid-1"])

    def test_the_service_delete_and_restore_return_the_new_trash(self):
        backend = mail.Mail(config=self.config)
        result = backend.delete_message({"uid": "uid-2", "subject": "Newer"})
        self.assertTrue(result["ok"])
        self.assertEqual([e["uid"] for e in result["messages"]], ["uid-2"])
        result = backend.restore_message("uid-2")
        self.assertTrue(result["ok"])
        self.assertEqual(result["messages"], [])

    def test_a_message_without_an_id_is_refused(self):
        backend = mail.Mail(config=self.config)
        result = backend.delete_message({})
        self.assertFalse(result["ok"])
        self.assertEqual(mail.load_trash(), [])

    # -- emptying the trash: the one path that writes to the account --------

    def write_config(self, **extra):
        config = {
            "host": "mail.example.org",
            "protocol": "pop3",
            "port": 995,
            "security": "ssl",
            "username": "user@example.org",
            "password": "secret",
        }
        config.update(extra)
        mail.save_config_dict(config)

    def deleting_client(self, allow_delete=True):
        connection = FakePop3Connection(self.messages, ["uid-1", "uid-2"],
                                        allow_delete=allow_delete)
        return connection, FakePop3Client(connection)

    def test_deleting_on_the_server_sends_dele_for_exactly_these_messages(self):
        connection, client = self.deleting_client()
        deleted, missing = mail.pop3_delete_messages(
            self.config, ["uid-2"], client_factory=lambda config: client
        )
        self.assertEqual(deleted, ["uid-2"])
        self.assertEqual(missing, [])
        self.assertEqual(connection.deleted, [2])  # POP3 numbers, not uids
        # QUIT is what makes the deletion real.
        self.assertTrue(connection.quit_called)

    def test_a_message_the_server_no_longer_has_is_reported_as_missing(self):
        connection, client = self.deleting_client()
        deleted, missing = mail.pop3_delete_messages(
            self.config, ["uid-2", "uid-404"],
            client_factory=lambda config: client
        )
        self.assertEqual(deleted, ["uid-2"])
        self.assertEqual(missing, ["uid-404"])
        self.assertEqual(connection.deleted, [2])

    def test_a_failure_closes_without_quit_so_nothing_is_deleted(self):
        connection, client = self.deleting_client(allow_delete=False)
        with self.assertRaises(AssertionError):
            mail.pop3_delete_messages(self.config, ["uid-2"],
                                      client_factory=lambda config: client)
        self.assertFalse(connection.quit_called)
        self.assertTrue(connection.closed_without_quit)

    def test_emptying_the_trash_clears_what_the_server_confirmed(self):
        self.write_config()
        mail.move_to_trash({"uid": "uid-2", "subject": "Newer"})
        mail.move_to_trash({"uid": "uid-9", "subject": "Already gone"})
        original = mail.pop3_delete_messages
        mail.pop3_delete_messages = lambda config, uids: (["uid-2"], ["uid-9"])
        try:
            result = mail.empty_trash()
        finally:
            mail.pop3_delete_messages = original
        self.assertTrue(result["ok"])
        self.assertEqual(result["deleted"], ["uid-2"])
        self.assertEqual(result["missing"], ["uid-9"])
        # Both are gone from the trash: one deleted, one no longer on the
        # server and therefore unshowable.
        self.assertEqual(mail.load_trash(), [])
        self.assertEqual(result["messages"], [])

    def test_a_failure_while_emptying_keeps_the_trash(self):
        self.write_config()
        mail.move_to_trash({"uid": "uid-2", "subject": "Newer"})
        original = mail.pop3_delete_messages

        def kaatuu(config, uids):
            raise mail.MailError("Yhteys palvelimeen epäonnistui.")

        mail.pop3_delete_messages = kaatuu
        try:
            result = mail.empty_trash()
        finally:
            mail.pop3_delete_messages = original
        self.assertFalse(result["ok"])
        self.assertIn("Yhteys palvelimeen", result["error"])
        self.assertEqual([e["uid"] for e in mail.load_trash()], ["uid-2"])

    def test_emptying_an_empty_trash_does_nothing(self):
        self.write_config()
        result = mail.empty_trash()
        self.assertTrue(result["ok"])
        self.assertEqual(result["deleted"], [])


class SignalTests(unittest.TestCase):
    def setUp(self):
        self.recorder = RecordingPyOtherSide()
        self.previous = mail.pyotherside
        mail.pyotherside = self.recorder

    def tearDown(self):
        mail.pyotherside = self.previous

    def test_list_inbox_emits_busy_and_message_list(self):
        backend = mail.Mail(config={"host": "imap.example.org"})
        original = mail.imap_inbox_list
        mail.imap_inbox_list = lambda config, limit: [{"uid": 1}]
        previous_loader = mail.load_config_dict
        mail.load_config_dict = lambda: {"host": "imap.example.org"}
        try:
            result = backend.list_inbox(10)
        finally:
            mail.imap_inbox_list = original
            mail.load_config_dict = previous_loader
        self.assertTrue(result["ok"])
        self.assertEqual(self.recorder.only("busy"), [(True,), (False,)])
        self.assertEqual(self.recorder.only("messageList"), [([{"uid": 1}],)])

    def test_errors_are_reported_as_a_signal(self):
        backend = mail.Mail(config={"host": "imap.example.org"})
        original = mail.imap_inbox_list
        previous_loader = mail.load_config_dict
        mail.load_config_dict = lambda: {"host": "imap.example.org"}

        def explode(config, limit):
            raise mail.MailError(
                "Kirjautuminen epäonnistui. Tarkista käyttäjätunnus ja salasana."
            )

        mail.imap_inbox_list = explode
        try:
            result = backend.list_inbox(10)
        finally:
            mail.imap_inbox_list = original
            mail.load_config_dict = previous_loader
        self.assertFalse(result["ok"])
        self.assertIn("Kirjautuminen epäonnistui", result["error"])
        self.assertEqual(
            self.recorder.only("error"),
            [("Kirjautuminen epäonnistui. Tarkista käyttäjätunnus ja salasana.",)],
        )

    def test_unexpected_errors_do_not_escape(self):
        backend = mail.Mail(config={})
        previous_loader = mail.load_config_dict
        mail.load_config_dict = lambda: {}
        original = mail.imap_inbox_list

        def explode(config, limit):
            raise RuntimeError("boom")

        mail.imap_inbox_list = explode
        try:
            result = backend.list_inbox(10)
        finally:
            mail.imap_inbox_list = original
            mail.load_config_dict = previous_loader
        self.assertFalse(result["ok"])
        self.assertIn("boom", result["error"])


if __name__ == "__main__":
    unittest.main()
