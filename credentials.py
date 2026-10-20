# Sähke - mail client for Ubuntu Touch
# Copyright (C) 2026 Reijo Kinnunen
#
# SPDX-License-Identifier: GPL-3.0-or-later
"""Where the account password is kept: the keyring, if it is reachable.

The phone has no ``secretstorage`` Python package and no ``Secret`` GIR
typelib, but it does have ``python-dbus``, and ``org.freedesktop.secrets`` is
running there (gnome-keyring). So the Secret Service is spoken directly over
D-Bus: a plain session, one item per account.

Everything here is best effort. If the service is missing, locked or refused
by the click sandbox, these functions return ``None``/``False`` and the caller
falls back to the app's own settings file. The app must never fail to start
because a keyring is not there.
"""

import os

SERVICE = "org.freedesktop.secrets"
SERVICE_PATH = "/org/freedesktop/secrets"
SERVICE_IFACE = "org.freedesktop.Secret.Service"
APPLICATION = "fi.reijo.sahkoposti"

_tried = False
_works = False


def _connection():
    """(service, session) or an exception if the keyring cannot be used."""
    import dbus  # imported here so the module loads without it

    # Without a bus address there is nothing to connect to; this also keeps
    # the test suite quick on a machine that has no session.
    if not os.environ.get("DBUS_SESSION_BUS_ADDRESS"):
        raise RuntimeError("no session bus")

    bus = dbus.SessionBus()
    obj = bus.get_object(SERVICE, SERVICE_PATH)
    service = dbus.Interface(obj, SERVICE_IFACE)
    _output, session = service.OpenSession(
        "plain", dbus.String("", variant_level=1)
    )
    return service, session


def available():
    """Is the keyring usable here? Asked once, then remembered."""
    global _tried, _works
    if not _tried:
        _tried = True
        try:
            _connection()
            _works = True
        except Exception:  # noqa: BLE001 - any obstacle means "no"
            _works = False
    return _works


def _attributes(username):
    import dbus

    return dbus.Dictionary(
        {"application": APPLICATION, "account": str(username or "")},
        signature="ss",
    )


def store(username, password):
    """Put the password in the keyring; True if it went in."""
    if not password:
        return False
    try:
        import dbus

        service, session = _connection()
        properties = dbus.Dictionary(
            {
                "org.freedesktop.Secret.Item.Label": "Sähke: %s" % username,
                "org.freedesktop.Secret.Item.Attributes": _attributes(username),
            },
            signature="sv",
        )
        secret = dbus.Struct(
            (
                dbus.ObjectPath(session),
                dbus.Array([], signature="y"),
                dbus.ByteArray(password.encode("utf-8")),
                "text/plain; charset=utf8",
            ),
            signature="oayays",
        )
        _item, prompt = service.CreateItem(properties, secret, True)
        # A prompt means the collection wants to ask the user something; this
        # app cannot show that, so count it as "not stored".
        return str(prompt) == "/"
    except Exception:  # noqa: BLE001
        return False


def lookup(username):
    """The stored password, or None."""
    try:
        import dbus

        service, session = _connection()
        unlocked, _locked = service.SearchItems(_attributes(username))
        if not len(unlocked):
            return None
        secrets = service.GetSecrets(unlocked, dbus.ObjectPath(session))
        for _path, secret in secrets.items():
            return bytes(bytearray(secret[2])).decode("utf-8")
    except Exception:  # noqa: BLE001
        return None
    return None


def forget(username):
    """Remove the stored password; True if nothing is left behind."""
    try:
        service, _session = _connection()
        unlocked, _locked = service.SearchItems(_attributes(username))
        for path in unlocked:
            service.DeleteItem(path)
        return True
    except Exception:  # noqa: BLE001
        return False
