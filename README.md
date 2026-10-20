# Sähke

Sähke is a native mail client for Ubuntu Touch 24.04. It is written in QML
and Python (PyOtherSide) and runs as a confined click. The user interface is
available in English (default) and Finnish, selected in Settings.

## Features

- one POP3 or IMAP account, SSL/TLS or STARTTLS
- inbox list and message reading; reading never marks a message as read
- sending and replying through SMTP
- a local trash with restore; emptying the trash deletes the selected
  messages on the server only after a confirmation
- two Revontuli themes (red and green), selected in Settings
- English and Finnish UI, including dialogs and error messages

## Requirements

- Ubuntu Touch 24.04 (Lomiri), click framework `ubuntu-touch-24.04-2.x`
- network access to the configured mail server

## Build

```sh
sudo apt install click python3
./tools/build.sh
```

The package is written to `dist/fi.reijo.sahkoposti_0.4.0_all.click`.
The build script uses the unpacked `click` tool from the Ubuntu archive if
the system does not have one.

## Install

```sh
click install --user phablet --allow-unauthenticated \
  dist/fi.reijo.sahkoposti_0.4.0_all.click
```

The app is installed for the `phablet` user, like other Ubuntu Touch clicks.

## Privacy

Sähke contains no analytics, advertising or third-party services. It
connects only to the mail server configured by the user.

The account password is stored in the app's own `config.json` (mode 0600)
because a confined click cannot use the desktop keyring on this Ubuntu Touch
version. The password is never sent anywhere except to the configured mail
server. The local trash contains only message metadata and stays on the
device; deleting a message there does not change the server.

## Limitations

- one account
- no attachments open/save, search, offline cache, background
  notifications or multiple accounts yet
- some providers do not offer IMAP; POP3 works when the provider supports it

Sähke is an independent project and is not an official UBports application.

## License

Sähke's own code is **GPL-3.0-or-later**; the full text is `LICENSE`.
The theme `.qml` files are **LGPL-3.0-only** derivatives of Canonical Ltd.'s
Lomiri themes, and the chevron artwork is **CC-BY-SA-3.0** (Canonical Ltd.,
unmodified). The licence texts travel with the theme modules; see
`THIRD_PARTY_NOTICES.md` for attribution and evidence.

## Releases

Release packages and checksums:
<https://github.com/reijokin-sys/Sahke/releases>

The source is at <https://github.com/reijokin-sys/Sahke>.
