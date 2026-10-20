# Sähke - mail client for Ubuntu Touch
# Copyright (C) 2026 Reijo Kinnunen
#
# SPDX-License-Identifier: GPL-3.0-or-later
"""IMAP backend for the Sähke app (fi.reijo.sahkoposti).

The QML user interface talks to this module through PyOtherSide: it imports
``mail`` and calls the module level functions at the bottom of this file.
PyOtherSide runs every call in its own worker thread, so the IMAP work never
blocks the user interface. Results are delivered both as PyOtherSide signals
(``config``, ``busy``, ``messageList``, ``messageBody``, ``error``) and as the
return value of the call.

The app is deliberately read-only in this phase: mailboxes are opened with
``readonly=True`` and message bodies are fetched with ``BODY.PEEK``, so
nothing in the account is modified and no message is marked as read.
"""

import email
import email.utils
import imaplib
import json
import os
import poplib
import re
import smtplib
import socket
import ssl
from datetime import datetime, timezone
from email.header import decode_header, make_header
from html.parser import HTMLParser
from email.message import EmailMessage

import credentials

try:  # PyOtherSide only exists inside the Ubuntu Touch app sandbox.
    import pyotherside
except ImportError:  # pragma: no cover - used by the host unit tests

    class _NullPyOtherSide(object):
        """Stand-in so the module can be imported and tested on a computer."""

        @staticmethod
        def send(*args, **kwargs):
            return None

    pyotherside = _NullPyOtherSide()


APP_ID = "fi.reijo.sahkoposti"
APP_NAME = "Sähke"
DEFAULT_LIST_LIMIT = 50
MAX_LIST_LIMIT = 500
IMAP_PORTS = {"ssl": 993, "starttls": 143}
POP3_PORTS = {"ssl": 995, "starttls": 110}
SMTP_PORTS = {"ssl": 465, "starttls": 587, "plain": 25}
PROTOCOLS = ("imap", "pop3")
CONNECT_TIMEOUT = 30
SECURITIES = ("ssl", "starttls")
SMTP_SECURITIES = ("ssl", "starttls", "plain")


def default_port(protocol, security):
    ports = POP3_PORTS if protocol == "pop3" else IMAP_PORTS
    return ports.get(security, 0)


def default_smtp_port(security):
    """The usual SMTP port for the transport in question."""
    return SMTP_PORTS.get(security, SMTP_PORTS["ssl"])


def config_protocol(config):
    protocol = (config.get("protocol") or "imap").strip().lower()
    return protocol if protocol in PROTOCOLS else "imap"


class MailError(Exception):
    """An expected, user facing error (shown in the UI as it is)."""


def _as_int(value, default):
    try:
        if value is None or value == "":
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def server_text(error):
    """The server's own words from an imaplib error (bytes or text)."""
    parts = []
    for argument in getattr(error, "args", ()) or ():
        if isinstance(argument, bytes):
            parts.append(argument.decode("utf-8", "replace"))
        else:
            parts.append(str(argument))
    return " ".join(parts).strip()


def login_failed_message(error):
    """Say what the server said, so a wrong password is not a dead end."""
    said = server_text(error)
    if not said:
        return "Kirjautuminen epäonnistui. Tarkista käyttäjätunnus ja salasana."
    return ("Kirjautuminen epäonnistui. Tarkista käyttäjätunnus ja salasana."
            "\nPalvelin sanoi: %s"
            % said)


# --------------------------------------------------------------------------
# Settings
# --------------------------------------------------------------------------


def data_dir():
    """Return the directory the app may write to.

    Inside the click sandbox ``XDG_DATA_HOME`` already points at the app's own
    data directory; outside of it (host unit tests) the app's sub directory of
    ``~/.local/share`` is used. ``SAHKOPOSTI_DATA_DIR`` overrides both, which
    is what the tests use.
    """
    override = os.environ.get("SAHKOPOSTI_DATA_DIR")
    if override:
        return override
    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg and os.path.basename(xdg.rstrip("/")) == APP_ID:
        return xdg
    base = xdg or os.path.join(os.path.expanduser("~"), ".local", "share")
    return os.path.join(base, APP_ID)


def config_path():
    return os.path.join(data_dir(), "config.json")


def load_config_dict():
    """Read the settings file; a missing or broken file means "not set up"."""
    try:
        with open(config_path(), "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    # The password may live in the keyring instead of the file (see
    # credentials.py); with no keyring this is simply skipped.
    if not data.get("password") and data.get("username"):
        if credentials.available():
            stored = credentials.lookup(data.get("username"))
            if stored:
                data["password"] = stored
    return data


def save_config_dict(config):
    """Write the settings file atomically with 0600 permissions.

    When a keyring is available the password goes there and the file only
    records that it did - a copy of the file is then not a password.
    """
    stored = dict(config)
    password = stored.get("password") or ""
    username = stored.get("username") or ""
    if password and username and credentials.available():
        if credentials.store(username, password):
            stored.pop("password", None)
            stored["password_in_keyring"] = True
        else:
            stored["password_in_keyring"] = False
    elif password:
        stored["password_in_keyring"] = False
    directory = data_dir()
    os.makedirs(directory, mode=0o700, exist_ok=True)
    path = config_path()
    temporary = path + ".tmp"
    handle = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(handle, "w", encoding="utf-8") as stream:
        json.dump(stored, stream, indent=2, sort_keys=True)
        stream.write("\n")
    os.replace(temporary, path)
    os.chmod(path, 0o600)
    return path


# --------------------------------------------------------------------------
# The trash: the messages deleted in this app only
# --------------------------------------------------------------------------
#
# POP3 has no folders and no trash, and a real ``DELE`` would remove the
# message from every client for good - there is no undo and no server-side
# trash to fall back on. So "delete" here moves the message into the app's own
# trash: the mailbox is never touched, the message can still be read and it
# can be put back. Nothing is destroyed anywhere (the user's choice,
# 2026-10-15).


def trash_path():
    """The file that holds the messages deleted in this app."""
    return os.path.join(data_dir(), "trash.json")


def load_trash():
    """The trashed entries, newest deletion first; a broken file means none."""
    try:
        with open(trash_path(), "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return []
    if not isinstance(data, list):
        return []
    return [
        entry
        for entry in data
        if isinstance(entry, dict) and entry.get("uid") not in (None, "")
    ]


def save_trash(entries):
    """Write the trash atomically with 0600 permissions."""
    directory = data_dir()
    os.makedirs(directory, mode=0o700, exist_ok=True)
    path = trash_path()
    temporary = path + ".tmp"
    handle = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(handle, "w", encoding="utf-8") as stream:
        json.dump(entries, stream, indent=2)
        stream.write("\n")
    os.replace(temporary, path)
    os.chmod(path, 0o600)
    return path


def trash_uids(entries=None):
    """The uids in the trash as strings (they arrive as ``str`` or ``int``)."""
    if entries is None:
        entries = load_trash()
    return {str(entry["uid"]) for entry in entries}


def move_to_trash(entry):
    """Put one message in the app's trash; the newest deletion comes first."""
    uid = entry.get("uid")
    entries = [item for item in load_trash() if str(item.get("uid")) != str(uid)]
    saved = dict(entry)
    saved["deleted"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    entries.insert(0, saved)
    save_trash(entries)
    return entries


def restore_from_trash(uid):
    """Take one message out of the trash and return what is left."""
    entries = [item for item in load_trash() if str(item.get("uid")) != str(uid)]
    save_trash(entries)
    return entries


def public_config(config):
    """The part of the settings the user interface may see (no password)."""
    visible = dict(config)
    visible.pop("password", None)
    keyring = visible.pop("password_in_keyring", False)
    visible["has_password"] = bool(config.get("password"))
    if keyring:
        visible["password_location"] = "keyring"
    elif config.get("password"):
        visible["password_location"] = "file"
    else:
        visible["password_location"] = "none"
    visible["configured"] = bool(config.get("host") and config.get("username"))
    return visible


def normalise_config(host, port, security, username, password, previous=None,
                     smtp_host=None, smtp_port=None, smtp_security=None):
    previous = previous or {}
    security = (security or "ssl").strip().lower()
    if security not in SECURITIES:
        security = "ssl"
    protocol = (previous.get("protocol") or "imap")
    protocol = str(protocol).strip().lower()
    if protocol not in PROTOCOLS:
        protocol = "imap"
    config = {
        "host": (host or "").strip(),
        "port": _as_int(port, default_port(protocol, security)),
        "security": security,
        "protocol": protocol,
        "username": (username or "").strip(),
    }
    if config["port"] <= 0:
        config["port"] = default_port(protocol, security)
    # An empty password field in the settings page means "keep the old one".
    config["password"] = password if password else previous.get("password", "")
    # Sending needs a second server. It is nearly always the same host as the
    # incoming mail, so the sending host follows the incoming host until the
    # user sets one of their own: an empty host means "follow", and a stored
    # value that is still the previous incoming host is the auto-filled one
    # (this is what keeps an older settings file following the server).
    if smtp_host is None:
        resolved_host = (previous.get("smtp_host") or "").strip()
        if resolved_host == (previous.get("host") or "").strip():
            resolved_host = ""
    else:
        resolved_host = str(smtp_host).strip()
    config["smtp_host"] = resolved_host or config["host"]
    resolved_security = (
        previous.get("smtp_security") if smtp_security is None else smtp_security
    )
    resolved_security = str(resolved_security or "ssl").strip().lower()
    if resolved_security not in SMTP_SECURITIES:
        resolved_security = "ssl"
    config["smtp_security"] = resolved_security
    resolved_port = previous.get("smtp_port") if smtp_port is None else smtp_port
    resolved_port = _as_int(resolved_port, 0)
    if resolved_port <= 0:
        # An empty field follows the transport: 465, 587 or 25.
        resolved_port = default_smtp_port(resolved_security)
    config["smtp_port"] = resolved_port
    return config


def normalise_config_for(protocol, host, port, security, username, password,
                         previous=None, smtp_host=None, smtp_port=None,
                         smtp_security=None):
    """normalise_config with an explicit protocol (the settings page)."""
    previous = dict(previous or {})
    candidate = str(protocol or "imap").strip().lower()
    if candidate in PROTOCOLS:
        previous["protocol"] = candidate
        if not port:
            # The port follows the protocol when the field is left alone.
            port = default_port(candidate, (security or "ssl").lower())
    return normalise_config(host, port, security, username, password, previous,
                            smtp_host=smtp_host, smtp_port=smtp_port,
                            smtp_security=smtp_security)


# --------------------------------------------------------------------------
# Header and body decoding
# --------------------------------------------------------------------------


def decode_header_value(value):
    """Decode an RFC 2047 encoded header (``=?utf-8?B?...?=``) to text."""
    if value is None:
        return ""
    try:
        return str(make_header(decode_header(str(value))))
    except (LookupError, TypeError, ValueError):
        return str(value)


def format_address(value):
    """Return ``Name <address>`` for a From/To/Cc header."""
    decoded = decode_header_value(value)
    name, address = email.utils.parseaddr(decoded)
    if name and address:
        return "%s <%s>" % (name, address)
    return address or decoded.strip()


def format_date(value):
    """Turn a Date header into an ISO 8601 string ("" when unparsable)."""
    raw = decode_header_value(value).strip()
    if not raw:
        return ""
    try:
        parsed = email.utils.parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        return ""
    if parsed is None:
        return ""
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.isoformat()


class _HtmlToText(HTMLParser):
    """Enough of an HTML parser to turn a mail body into readable text."""

    BLOCK_TAGS = frozenset(
        (
            "address",
            "article",
            "blockquote",
            "br",
            "dd",
            "div",
            "dl",
            "dt",
            "h1",
            "h2",
            "h3",
            "h4",
            "h5",
            "h6",
            "hr",
            "li",
            "ol",
            "p",
            "pre",
            "section",
            "table",
            "td",
            "th",
            "tr",
            "ul",
        )
    )
    SKIP_TAGS = frozenset(("head", "script", "style", "title"))

    def __init__(self):
        HTMLParser.__init__(self, convert_charrefs=True)
        self._chunks = []
        self._skipping = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP_TAGS:
            self._skipping += 1
        elif tag in self.BLOCK_TAGS:
            self._chunks.append("\n")

    def handle_startendtag(self, tag, attrs):
        if tag in self.BLOCK_TAGS:
            self._chunks.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP_TAGS:
            self._skipping = max(0, self._skipping - 1)
        elif tag in self.BLOCK_TAGS:
            self._chunks.append("\n")

    def handle_data(self, data):
        if not self._skipping:
            self._chunks.append(data)

    def text(self):
        return "".join(self._chunks)


def html_to_text(html):
    parser = _HtmlToText()
    try:
        parser.feed(html)
        parser.close()
    except Exception:  # HTMLParser is forgiving; this is belt and braces
        return html
    text = parser.text()
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t\f\v]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _decode_part(part):
    payload = part.get_payload(decode=True)
    if payload is None:
        payload = part.get_payload()
        return payload if isinstance(payload, str) else ""
    charset = part.get_content_charset() or "utf-8"
    try:
        return payload.decode(charset, errors="replace")
    except (LookupError, TypeError):
        return payload.decode("utf-8", errors="replace")


def message_text(message):
    """Return the readable body: text/plain first, otherwise stripped HTML."""
    if message.is_multipart():
        plain = None
        html = None
        for part in message.walk():
            if part.is_multipart():
                continue
            disposition = str(part.get("Content-Disposition") or "").lower()
            if "attachment" in disposition:
                continue
            content_type = part.get_content_type()
            if content_type == "text/plain" and plain is None:
                plain = part
            elif content_type == "text/html" and html is None:
                html = part
        if plain is not None:
            return _decode_part(plain)
        if html is not None:
            return html_to_text(_decode_part(html))
        return ""
    if message.get_content_type() == "text/html":
        return html_to_text(_decode_part(message))
    return _decode_part(message)


def message_snippet(text, length=140):
    """One-line preview of a body, used in the message list."""
    flat = re.sub(r"\s+", " ", text or "").strip()
    if len(flat) <= length:
        return flat
    return flat[: length - 1].rstrip() + "\u2026"


def summarise(message):
    """The header information the message list shows."""
    return {
        "from": format_address(message.get("From")),
        "to": format_address(message.get("To")),
        "cc": format_address(message.get("Cc")),
        "subject": decode_header_value(message.get("Subject")).strip(),
        "date": format_date(message.get("Date")),
        "message_id": decode_header_value(message.get("Message-ID")).strip(),
    }


# --------------------------------------------------------------------------
# IMAP
# --------------------------------------------------------------------------


class ImapClient(object):
    """Opens one IMAP connection per operation."""

    def __init__(self, config, timeout=CONNECT_TIMEOUT, ssl_context=None):
        self.config = config or {}
        self.timeout = timeout
        # Only the tests pass a context of their own (they talk to a local
        # server with a self signed certificate); the app always verifies the
        # real certificate chain.
        self.ssl_context = ssl_context

    def connect(self):
        host = (self.config.get("host") or "").strip()
        if not host:
            raise MailError(
                "Tiliä ei ole vielä määritetty. Avaa Asetukset ja täytä "
                "palvelimen tiedot."
            )
        security = (self.config.get("security") or "ssl").strip().lower()
        if security not in SECURITIES:
            security = "ssl"
        port = _as_int(self.config.get("port"), default_port("imap", security))
        username = self.config.get("username") or ""
        password = self.config.get("password") or ""
        context = self.ssl_context or ssl.create_default_context()
        try:
            if security == "starttls":
                connection = imaplib.IMAP4(
                    host, port, timeout=self.timeout
                )
                connection.starttls(ssl_context=context)
            else:
                connection = imaplib.IMAP4_SSL(
                    host, port, ssl_context=context, timeout=self.timeout
                )
        except ssl.SSLError as error:
            raise MailError("TLS-virhe yhdistettäessä osoitteeseen %s: %s"
                            % (host, error))
        except (OSError, imaplib.IMAP4.error) as error:
            raise MailError(
                "Yhteys osoitteeseen %s:%s epäonnistui (%s)"
                % (host, port, error)
            )
        try:
            connection.login(username, password)
        except imaplib.IMAP4.error as error:
            self.close(connection)
            raise MailError(login_failed_message(error))
        except (OSError, ssl.SSLError) as error:
            self.close(connection)
            raise MailError("Yhteys katkesi kirjautumisen aikana: %s" % error)
        return connection

    @staticmethod
    def close(connection):
        try:
            connection.logout()
        except Exception:
            pass


class Pop3Client(object):
    """Opens one POP3 connection per operation.

    POP3 keeps a session state: messages are only removed when ``DELE`` is
    sent, and this client never sends it, so a session always ends with the
    mailbox exactly as it was.
    """

    def __init__(self, config, timeout=CONNECT_TIMEOUT, ssl_context=None):
        self.config = config or {}
        self.timeout = timeout
        self.ssl_context = ssl_context

    def connect(self):
        host = (self.config.get("host") or "").strip()
        if not host:
            raise MailError(
                "Tiliä ei ole vielä määritetty. Avaa Asetukset ja täytä "
                "palvelimen tiedot."
            )
        security = (self.config.get("security") or "ssl").strip().lower()
        if security not in SECURITIES:
            security = "ssl"
        port = _as_int(self.config.get("port"), default_port("pop3", security))
        username = self.config.get("username") or ""
        password = self.config.get("password") or ""
        context = self.ssl_context or ssl.create_default_context()
        try:
            if security == "starttls":
                connection = poplib.POP3(host, port, timeout=self.timeout)
                connection.stls(context=context)
            else:
                connection = poplib.POP3_SSL(
                    host, port, context=context, timeout=self.timeout
                )
        except ssl.SSLError as error:
            raise MailError("TLS-virhe yhdistettäessä osoitteeseen %s: %s"
                            % (host, error))
        except (OSError, poplib.error_proto) as error:
            raise MailError(
                "Yhteys osoitteeseen %s:%s epäonnistui (%s)"
                % (host, port, error)
            )
        try:
            connection.user(username)
            connection.pass_(password)
        except poplib.error_proto as error:
            self.close(connection)
            raise MailError(login_failed_message(error))
        except (OSError, ssl.SSLError) as error:
            self.close(connection)
            raise MailError("Yhteys katkesi kirjautumisen aikana: %s" % error)
        return connection

    @staticmethod
    def close(connection):
        try:
            connection.quit()
        except Exception:
            pass


_UID_RE = re.compile(rb"UID (\d+)")
_FLAGS_RE = re.compile(rb"FLAGS \(([^)]*)\)")
_SIZE_RE = re.compile(rb"RFC822\.SIZE (\d+)")
_HEADER_FIELDS = "(FROM TO SUBJECT DATE MESSAGE-ID)"


def parse_fetch_headers(responses):
    """Turn an ``imaplib`` FETCH response into a list of list entries."""
    messages = []
    for item in responses or []:
        if not isinstance(item, tuple) or len(item) != 2:
            continue
        meta, payload = item
        if isinstance(meta, str):
            meta = meta.encode("utf-8", "replace")
        uid_match = _UID_RE.search(meta)
        if not uid_match or not payload:
            continue
        flags_match = _FLAGS_RE.search(meta)
        size_match = _SIZE_RE.search(meta)
        header = email.message_from_bytes(payload)
        entry = summarise(header)
        entry.update(
            {
                "uid": int(uid_match.group(1)),
                "seen": b"\\Seen" in (flags_match.group(1) if flags_match else b""),
                "size": int(size_match.group(1)) if size_match else 0,
                "snippet": "",
            }
        )
        messages.append(entry)
    messages.sort(key=lambda message: message["uid"], reverse=True)
    return messages


def imap_inbox_list(config, limit=DEFAULT_LIST_LIMIT, client_factory=ImapClient):
    """The newest ``limit`` messages of INBOX, newest first."""
    limit = max(1, min(MAX_LIST_LIMIT, _as_int(limit, DEFAULT_LIST_LIMIT)))
    client = client_factory(config)
    connection = client.connect()
    try:
        status, data = connection.select("INBOX", readonly=True)
        if status != "OK":
            raise MailError("Saapuneet-kansiota ei voitu avata.")
        total = _as_int(data[0] if data else 0, 0)
        if total <= 0:
            return []
        first = max(1, total - limit + 1)
        status, data = connection.fetch(
            "%d:*" % first,
            "(UID FLAGS RFC822.SIZE BODY.PEEK[HEADER.FIELDS %s])"
            % _HEADER_FIELDS,
        )
        if status != "OK":
            raise MailError("Viestiluetteloa ei voitu lukea.")
        return parse_fetch_headers(data)
    finally:
        client.close(connection)


def imap_fetch_message(config, uid, client_factory=ImapClient):
    """One message with its readable body; never marks it as read."""
    client = client_factory(config)
    connection = client.connect()
    try:
        status, _data = connection.select("INBOX", readonly=True)
        if status != "OK":
            raise MailError("Saapuneet-kansiota ei voitu avata.")
        status, data = connection.uid(
            "FETCH", str(uid), "(UID FLAGS BODY.PEEK[])"
        )
        if status != "OK":
            raise MailError("Viestiä ei voitu hakea.")
        payload = None
        for item in data or []:
            if isinstance(item, tuple) and len(item) == 2:
                payload = item[1]
                break
        if payload is None:
            raise MailError("Viestiä ei löytynyt Saapuneet-kansiosta.")
        message = email.message_from_bytes(payload)
        result = summarise(message)
        text = message_text(message)
        result.update(
            {
                "uid": _as_int(uid, 0),
                "text": text,
                "snippet": message_snippet(text),
                "truncated": False,
                "attachments": _attachment_names(message),
            }
        )
        return result
    finally:
        client.close(connection)


def _attachment_names(message):
    names = []
    if not message.is_multipart():
        return names
    for part in message.walk():
        disposition = str(part.get("Content-Disposition") or "").lower()
        if "attachment" not in disposition:
            continue
        filename = part.get_filename()
        names.append(decode_header_value(filename) if filename else "(unnamed)")
    return names


# --------------------------------------------------------------------------
# POP3
# --------------------------------------------------------------------------


def parse_uidl(lines):
    """``{message number: unique id}`` from a POP3 UIDL response."""
    mapping = {}
    for line in lines or []:
        if isinstance(line, bytes):
            line = line.decode("utf-8", "replace")
        parts = line.split()
        if len(parts) >= 2 and parts[0].isdigit():
            mapping[int(parts[0])] = parts[1]
    return mapping


def parse_list_sizes(lines):
    sizes = {}
    for line in lines or []:
        if isinstance(line, bytes):
            line = line.decode("utf-8", "replace")
        parts = line.split()
        if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
            sizes[int(parts[0])] = int(parts[1])
    return sizes


def pop3_headers(connection, number):
    """The header block of one message; nothing is marked or deleted."""
    try:
        _response, lines, _octets = connection.top(number, 0)
    except poplib.error_proto:
        # Not every server offers TOP. RETR is the fallback and is just as
        # harmless: POP3 has no read state.
        _response, lines, _octets = connection.retr(number)
    return b"\r\n".join(lines) + b"\r\n\r\n"


def pop3_inbox_list(config, limit=DEFAULT_LIST_LIMIT, client_factory=Pop3Client):
    """The newest ``limit`` messages, newest first.

    POP3 numbers messages in arrival order, so the list is reversed. The
    unique id from UIDL is used as the message id, because the numbers change
    when messages are removed elsewhere.
    """
    limit = max(1, min(MAX_LIST_LIMIT, _as_int(limit, DEFAULT_LIST_LIMIT)))
    client = client_factory(config)
    connection = client.connect()
    try:
        _response, uidl_lines, _octets = connection.uidl()
        uidl = parse_uidl(uidl_lines)
        if not uidl:
            return []
        try:
            _response, list_lines, _octets = connection.list()
            sizes = parse_list_sizes(list_lines)
        except poplib.error_proto:
            sizes = {}
        # The messages in the app's own trash are left out of the list, so a
        # deleted message disappears without anything being sent to the server.
        hidden = trash_uids()
        numbers = [n for n in sorted(uidl, reverse=True)
                   if str(uidl[n]) not in hidden]
        messages = []
        for number in numbers[:limit]:
            header = email.message_from_bytes(pop3_headers(connection, number))
            entry = summarise(header)
            entry.update(
                {
                    "uid": uidl[number],
                    "seen": None,  # POP3 has no read state at all
                    "size": sizes.get(number, 0),
                    "snippet": "",
                }
            )
            messages.append(entry)
        return messages
    finally:
        client.close(connection)


def pop3_fetch_message(config, uid, client_factory=Pop3Client):
    """One message by its UIDL; it stays on the server untouched."""
    client = client_factory(config)
    connection = client.connect()
    try:
        _response, uidl_lines, _octets = connection.uidl()
        number = None
        for candidate, value in parse_uidl(uidl_lines).items():
            if str(value) == str(uid):
                number = candidate
                break
        if number is None:
            raise MailError("Viestiä ei löytynyt postilaatikosta.")
        _response, lines, _octets = connection.retr(number)
        message = email.message_from_bytes(b"\r\n".join(lines))
        result = summarise(message)
        text = message_text(message)
        result.update(
            {
                "uid": str(uid),
                "text": text,
                "snippet": message_snippet(text),
                "truncated": False,
                "attachments": _attachment_names(message),
            }
        )
        return result
    finally:
        client.close(connection)


# --------------------------------------------------------------------------
# QML facing API (the Mail class and its module level forwarders)
# --------------------------------------------------------------------------


# --------------------------------------------------------------------------
# Sending (SMTP)
# --------------------------------------------------------------------------


def pop3_delete_messages(config, uids, client_factory=Pop3Client):
    """Delete messages from the server for good - the one writing path.

    POP3 only marks a message with ``DELE``; the mailbox really changes when
    the session ends with ``QUIT``. So a failure before that leaves the
    mailbox exactly as it was: the connection is closed without ``QUIT``.

    Returns ``(deleted, missing)`` where ``missing`` holds the uids the server
    no longer has (deleted in another client).
    """
    client = client_factory(config)
    connection = client.connect()
    deleted, missing = [], []
    try:
        _response, lines, _octets = connection.uidl()
        numbers = {uid: number for number, uid in parse_uidl(lines).items()}
        for uid in uids:
            number = numbers.get(str(uid))
            if number is None:
                missing.append(str(uid))
                continue
            connection.dele(number)
            deleted.append(str(uid))
    except Exception:
        try:
            connection.close()  # no QUIT: the marks are dropped
        except Exception:  # noqa: BLE001
            pass
        raise
    client.close(connection)  # QUIT - this is what makes it permanent
    return deleted, missing


def imap_delete_messages(config, uids, client_factory=ImapClient):
    """Delete messages for good over IMAP: ``\\Deleted`` + ``EXPUNGE``.

    This is the only place the app opens the mailbox for writing.
    """
    client = client_factory(config)
    connection = client.connect()
    try:
        status, _data = connection.select("INBOX")  # read-write, on purpose
        if status != "OK":
            raise MailError("Saapuneet-kansiota ei voitu avata kirjoittamista "
                            "varten.")
        deleted = []
        for uid in uids:
            status, _data = connection.uid(
                "STORE", str(uid), "+FLAGS", "(\\Deleted)"
            )
            if status == "OK":
                deleted.append(str(uid))
        status, _data = connection.expunge()
        if status != "OK":
            raise MailError("Viestien poistaminen palvelimelta epäonnistui.")
        return deleted, []
    finally:
        client.close(connection)


class SmtpClient(object):
    """A logged in SMTP session; opened and closed for every message."""

    def __init__(self, config, timeout=CONNECT_TIMEOUT, ssl_context=None):
        self.config = config
        self.timeout = timeout
        self.ssl_context = ssl_context or ssl.create_default_context()
        self.connection = None

    def connect(self):
        config = self.config
        host = (config.get("smtp_host") or config.get("host") or "").strip()
        security = (config.get("smtp_security") or "ssl").strip().lower()
        if security not in SMTP_SECURITIES:
            security = "ssl"
        port = _as_int(config.get("smtp_port"), default_smtp_port(security))
        if not host:
            raise MailError("Lähettävää palvelinta ei ole asetettu. Avaa "
                            "Asetukset.")
        try:
            if security == "ssl":
                connection = smtplib.SMTP_SSL(
                    host, port, timeout=self.timeout, context=self.ssl_context
                )
            else:
                connection = smtplib.SMTP(host, port, timeout=self.timeout)
                connection.ehlo()
                if security == "starttls":
                    connection.starttls(context=self.ssl_context)
                    connection.ehlo()
        except socket.timeout:
            raise MailError("Yhteys osoitteeseen %s:%s aikakatkaistiin."
                            % (host, port))
        except ssl.SSLError as error:
            raise MailError("Suojattu yhteys osoitteeseen %s:%s epäonnistui "
                            "(%s)."
                            % (host, port, error))
        except (OSError, smtplib.SMTPException) as error:
            raise MailError("Yhteys osoitteeseen %s:%s epäonnistui (%s)."
                            % (host, port, error))
        try:
            connection.login(config.get("username") or "", config.get("password") or "")
        except smtplib.SMTPAuthenticationError as error:
            try:
                connection.close()
            except Exception:  # noqa: BLE001 - the error above is the one that counts
                pass
            raise MailError(login_failed_message(error))
        except smtplib.SMTPException as error:
            try:
                connection.close()
            except Exception:  # noqa: BLE001
                pass
            raise MailError(
                "Kirjautuminen epäonnistui. Tarkista käyttäjätunnus ja "
                "salasana.\nPalvelin sanoi: %s"
                % server_text(error)
            )
        self.connection = connection
        return connection

    def close(self):
        connection = self.connection
        self.connection = None
        if connection is None:
            return
        try:
            connection.quit()
        except Exception:  # noqa: BLE001 - closing must never raise
            try:
                connection.close()
            except Exception:  # noqa: BLE001
                pass


def build_message(config, to, subject, body, in_reply_to=None, references=None):
    """The message that is about to be sent, as an EmailMessage."""
    message = EmailMessage()
    message["From"] = (config.get("username") or "").strip()
    if isinstance(to, (list, tuple)):
        message["To"] = ", ".join(address.strip() for address in to if address)
    else:
        message["To"] = (to or "").strip()
    message["Subject"] = subject or ""
    message["Date"] = email.utils.formatdate(localtime=True)
    domain = "localhost"
    username = config.get("username") or ""
    if "@" in username:
        domain = username.split("@")[-1] or "localhost"
    message["Message-ID"] = email.utils.make_msgid(domain=domain)
    if in_reply_to:
        message["In-Reply-To"] = in_reply_to
    if references:
        message["References"] = references
    message.set_content(body or "")
    return message


def smtp_send(config, to, subject, body, in_reply_to=None, references=None,
              client_factory=SmtpClient):
    """Send one message. Raises MailError with a readable reason on failure."""
    if not (config.get("host") and config.get("username")):
        raise MailError("Tiliä ei ole vielä määritetty. Avaa ensin Asetukset.")
    if not (to or "").strip():
        raise MailError("Anna vastaanottajan osoite.")
    if not config.get("password"):
        raise MailError("Salasana puuttuu. Avaa Asetukset ja tallenna se.")
    message = build_message(config, to, subject, body, in_reply_to, references)
    client = client_factory(config)
    try:
        connection = client.connect()
        connection.send_message(message)
    except smtplib.SMTPRecipientsRefused as error:
        raise MailError("Palvelin hylkäsi vastaanottajan osoitteen: %s"
                        % ", ".join(sorted(error.recipients.keys())))
    except smtplib.SMTPSenderRefused as error:
        raise MailError("Palvelin hylkäsi lähettäjän osoitteen.\n"
                        "Palvelin sanoi: %s"
                        % server_text(error))
    except smtplib.SMTPException as error:
        raise MailError("Palvelin hylkäsi viestin.\nPalvelin sanoi: %s"
                        % server_text(error))
    finally:
        client.close()
    return message


class Mail(object):
    """The backend object; the module level functions below forward to it."""

    def __init__(self, config=None):
        self.config = config if config is not None else load_config_dict()

    # -- settings ---------------------------------------------------------

    def load_config(self):
        """The settings; a password still in the file moves to the keyring."""
        self.config = load_config_dict()
        if (self.config.get("password") and self.config.get("username")
                and not self.config.get("password_in_keyring")
                and credentials.available()):
            if credentials.store(self.config["username"], self.config["password"]):
                self.config["password_in_keyring"] = True
                try:
                    save_config_dict(self.config)  # now without the password
                except OSError:
                    pass
        visible = public_config(self.config)
        # So the journal says where the password ended up (and whether the
        # click sandbox allowed the keyring at all).
        pyotherside.send("credentials", visible.get("password_location", "none"))
        pyotherside.send("config", visible)
        return visible

    def configure(self, host, port, security, username, password,
                  protocol="imap", smtp_host=None, smtp_port=None,
                  smtp_security=None):
        config = normalise_config_for(
            protocol, host, port, security, username, password,
            previous=self.config, smtp_host=smtp_host, smtp_port=smtp_port,
            smtp_security=smtp_security,
        )
        self.config = config
        try:
            save_config_dict(config)
        except OSError as error:
            message = "Asetuksia ei voitu tallentaa: %s" % error
            pyotherside.send("error", message)
            return {"ok": False, "error": message}
        visible = public_config(config)
        pyotherside.send("config", visible)
        return {"ok": True, "config": visible}

    # -- mail -------------------------------------------------------------

    def list_inbox(self, limit=DEFAULT_LIST_LIMIT):
        pyotherside.send("busy", True)
        try:
            config = load_config_dict()
            if config_protocol(config) == "pop3":
                messages = pop3_inbox_list(config, limit)
            else:
                messages = imap_inbox_list(config, limit)
        except MailError as error:
            pyotherside.send("error", str(error))
            return {"ok": False, "error": str(error)}
        except Exception as error:  # never let a traceback reach QML
            pyotherside.send("error", "Odottamaton virhe: %s" % error)
            return {"ok": False, "error": str(error)}
        finally:
            pyotherside.send("busy", False)
        pyotherside.send("messageList", messages)
        return {"ok": True, "messages": messages}

    def fetch_message(self, uid):
        pyotherside.send("busy", True)
        try:
            config = load_config_dict()
            if config_protocol(config) == "pop3":
                message = pop3_fetch_message(config, uid)
            else:
                message = imap_fetch_message(config, uid)
        except MailError as error:
            pyotherside.send("error", str(error))
            return {"ok": False, "error": str(error)}
        except Exception as error:
            pyotherside.send("error", "Odottamaton virhe: %s" % error)
            return {"ok": False, "error": str(error)}
        finally:
            pyotherside.send("busy", False)
        pyotherside.send("messageBody", message)
        return {"ok": True, "message": message}

    # -- the trash ---------------------------------------------------------

    def list_trash(self):
        """The messages this app has deleted. Nothing is sent to the server."""
        entries = load_trash()
        pyotherside.send("trashList", entries)
        return {"ok": True, "messages": entries}

    def delete_message(self, message):
        """Move a message into the app's own trash; the mailbox is untouched."""
        entry = dict(message) if isinstance(message, dict) else {"uid": message}
        if entry.get("uid") in (None, ""):
            return {"ok": False, "error": "Viestillä ei ole tunnistetta."}
        try:
            entries = move_to_trash(entry)
        except OSError as error:
            text = "Roskakoria ei voitu tallentaa: %s" % error
            pyotherside.send("error", text)
            return {"ok": False, "error": text}
        pyotherside.send("trashed", entry.get("uid"))
        return {"ok": True, "uid": entry.get("uid"), "messages": entries}

    def restore_message(self, uid):
        """Take a message out of the trash, so it shows up in the inbox again."""
        try:
            entries = restore_from_trash(uid)
        except OSError as error:
            text = "Roskakoria ei voitu tallentaa: %s" % error
            pyotherside.send("error", text)
            return {"ok": False, "error": text}
        pyotherside.send("restored", uid)
        return {"ok": True, "uid": uid, "messages": entries}

    def empty_trash(self):
        """Delete the trashed messages from the server, for good.

        This is the only place this app writes to the account, it happens only
        when the user confirms it, and it cannot be undone: POP3 has no trash
        of its own and the message disappears for every client.
        """
        entries = load_trash()
        if not entries:
            return {"ok": True, "deleted": [], "missing": [], "messages": []}
        uids = [str(entry["uid"]) for entry in entries]
        config = load_config_dict()
        pyotherside.send("busy", True)
        try:
            if config_protocol(config) == "pop3":
                deleted, missing = pop3_delete_messages(config, uids)
            else:
                deleted, missing = imap_delete_messages(config, uids)
        except MailError as error:
            pyotherside.send("error", str(error))
            return {"ok": False, "error": str(error), "messages": entries}
        except Exception as error:  # never let a traceback reach QML
            text = "Odottamaton virhe: %s" % error
            pyotherside.send("error", text)
            return {"ok": False, "error": text, "messages": entries}
        finally:
            pyotherside.send("busy", False)
        # Whatever the server no longer has leaves the trash too: those
        # messages cannot be shown again anyway.
        gone = {str(uid) for uid in deleted} | {str(uid) for uid in missing}
        left = [entry for entry in entries if str(entry.get("uid")) not in gone]
        try:
            save_trash(left)
        except OSError as error:
            text = "Viestit poistettiin, mutta roskakoria ei voitu " \
                   "päivittää: %s" % error
            pyotherside.send("error", text)
            return {"ok": False, "error": text, "messages": entries}
        pyotherside.send("trashEmptied", {"deleted": len(deleted)})
        return {"ok": True, "deleted": deleted, "missing": missing,
                "messages": left}

    def send(self, to, subject, body, in_reply_to=None):
        """Send a message the user wrote (phase 3)."""
        pyotherside.send("busy", True)
        try:
            config = load_config_dict()
            smtp_send(config, to, subject, body, in_reply_to=in_reply_to)
        except MailError as error:
            pyotherside.send("error", str(error))
            return {"ok": False, "error": str(error)}
        except Exception as error:  # never let a traceback reach QML
            pyotherside.send("error", "Odottamaton virhe: %s" % error)
            return {"ok": False, "error": str(error)}
        finally:
            pyotherside.send("busy", False)
        pyotherside.send("sent", {"to": to, "subject": subject})
        return {"ok": True}


_BACKEND = Mail()


def load_config():
    return _BACKEND.load_config()


def configure(host, port, security, username, password, protocol="imap",
              smtp_host=None, smtp_port=None, smtp_security=None):
    return _BACKEND.configure(host, port, security, username, password, protocol,
                              smtp_host, smtp_port, smtp_security)


def list_inbox(limit=DEFAULT_LIST_LIMIT):
    return _BACKEND.list_inbox(limit)


def fetch_message(uid):
    return _BACKEND.fetch_message(uid)


def list_trash():
    return _BACKEND.list_trash()


def delete_message(message):
    return _BACKEND.delete_message(message)


def restore_message(uid):
    return _BACKEND.restore_message(uid)


def empty_trash():
    return _BACKEND.empty_trash()


def send_message(to, subject, body, in_reply_to=None):
    return _BACKEND.send(to, subject, body, in_reply_to)
