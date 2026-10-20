/*
 * Sähke - mail client for Ubuntu Touch
 * Copyright (C) 2026 Reijo Kinnunen
 *
 * SPDX-License-Identifier: GPL-3.0-or-later
 */

import QtQuick 2.7
import Lomiri.Components 1.3
import "fonts.js" as Fonts

Page {
    id: page

    property var config
    /// "punainen" or "vihrea": Sähke's own theme, not the phone's.
    property string themeKey: "punainen"

    signal saveRequested(var host, var port, var security, var username,
                         var password, var protocol, var smtpHost,
                         var smtpPort, var smtpSecurity)
    signal themeRequested(string key)

    header: SahkopostiHeader {
        id: header
        title: "Asetukset"
    }

    function defaultPort(protocol, security) {
        if (protocol === "pop3")
            return security === "starttls" ? "110" : "995"
        return security === "starttls" ? "143" : "993"
    }

    function defaultSmtpPort(security) {
        if (security === "starttls")
            return "587"
        if (security === "plain")
            return "25"
        return "465"
    }

    // Switching the protocol or the security moves the port to the new
    // default, but only when the field still holds a well known value - a
    // port someone typed themselves is left alone.
    function resetPortIfStandard() {
        var known = ["", "993", "995", "143", "110"]
        if (known.indexOf(portField.text) >= 0)
            portField.text = ""
    }

    function resetSmtpPortIfStandard() {
        var known = ["", "465", "587", "25"]
        if (known.indexOf(smtpPortField.text) >= 0)
            smtpPortField.text = ""
    }

    // The sending server follows the incoming one until it is set by hand, so
    // a stored value that is still the incoming host is shown as empty.
    function smtpHostValue() {
        var stored = page.currentField("smtp_host", "")
        return stored === page.currentField("host", "") ? "" : stored
    }

    function currentField(name, fallback) {
        if (page.config && page.config[name] !== undefined
                && page.config[name] !== null)
            return String(page.config[name])
        return fallback
    }

    Flickable {
        id: settingsFlickable
        anchors {
            top: header.bottom
            left: parent.left
            right: parent.right
            bottom: parent.bottom
        }
        clip: true
        contentWidth: width
        contentHeight: column.height + units.gu(4)

        Column {
            id: column
            x: units.gu(2)
            y: units.gu(2)
            width: parent.width - units.gu(4)
            spacing: units.gu(2)

            Label {
                text: "Teema"
                font.pixelSize: Fonts.bigger(FontUtils.sizeToPixels("large"))
            }

            OptionSelector {
                id: themeSelector
                width: parent.width
                expanded: false
                model: ["Revontuli punainen", "Revontuli vihreä"]
                selectedIndex: page.themeKey === "vihrea" ? 1 : 0
                onSelectedIndexChanged: {
                    var key = selectedIndex === 1 ? "vihrea" : "punainen"
                    if (key !== page.themeKey)
                        page.themeRequested(key)
                }
            }

            Label {
                width: parent.width
                wrapMode: Text.WordWrap
                font.pixelSize: Fonts.bigger(FontUtils.sizeToPixels("small"))
                opacity: 0.7
                text: "Sähkeellä on omat värinsä - puhelimen teema ei "
                      + "muuta niitä."
            }

            Label {
                text: "Tili"
                font.pixelSize: Fonts.bigger(FontUtils.sizeToPixels("large"))
            }

            TextField {
                id: hostField
                width: parent.width
                placeholderText: "IMAP-palvelin, esim. imap.esimerkki.fi"
                text: page.currentField("host", "")
                font.pixelSize: Fonts.bigger(FontUtils.sizeToPixels("medium"))
            }

            TextField {
                id: userField
                width: parent.width
                placeholderText: "Käyttäjätunnus"
                text: page.currentField("username", "")
                inputMethodHints: Qt.ImhNoAutoUppercase | Qt.ImhNoPredictiveText
                font.pixelSize: Fonts.bigger(FontUtils.sizeToPixels("medium"))
            }

            TextField {
                id: passwordField
                width: parent.width
                placeholderText: page.config && page.config.has_password
                               ? "Salasana (ei muutettu)"
                               : "Salasana"
                echoMode: showPassword.checked ? TextInput.Normal
                                               : TextInput.Password
                inputMethodHints: Qt.ImhNoAutoUppercase | Qt.ImhNoPredictiveText
                font.pixelSize: Fonts.bigger(FontUtils.sizeToPixels("medium"))
            }

            CheckBox {
                id: showPassword
                text: "Näytä salasana"
                checked: false
            }

            Label {
                text: "Protokolla"
                font.pixelSize: Fonts.bigger(FontUtils.sizeToPixels("medium"))
            }

            OptionSelector {
                id: protocolSelector
                width: parent.width
                expanded: false
                model: ["IMAP", "POP3"]
                selectedIndex: page.currentField("protocol", "imap") === "pop3"
                               ? 1 : 0
                onSelectedIndexChanged: page.resetPortIfStandard()
            }

            Label {
                width: parent.width
                wrapMode: Text.WordWrap
                font.pixelSize: Fonts.bigger(FontUtils.sizeToPixels("small"))
                opacity: 0.7
                text: "Jätä salasana tyhjäksi, jos haluat säilyttää "
                      + "tallennetun. Rastita \"Näytä salasana\", jos haluat "
                      + "tarkistaa kirjoittamasi."
            }

            TextField {
                id: portField
                width: parent.width
                placeholderText: page.defaultPort(
                    protocolSelector.selectedIndex === 1 ? "pop3" : "imap",
                    securitySelector.selectedIndex === 1 ? "starttls" : "ssl")
                text: page.currentField("port", "")
                inputMethodHints: Qt.ImhDigitsOnly
                font.pixelSize: Fonts.bigger(FontUtils.sizeToPixels("medium"))
            }

            Label {
                text: "Yhteyden suojaus"
                font.pixelSize: Fonts.bigger(FontUtils.sizeToPixels("medium"))
            }

            OptionSelector {
                id: securitySelector
                width: parent.width
                expanded: false
                model: ["SSL/TLS", "STARTTLS"]
                selectedIndex: page.currentField("security", "ssl") === "starttls"
                               ? 1 : 0
                onSelectedIndexChanged: page.resetPortIfStandard()
            }

            Label {
                text: "Lähettävä palvelin"
                font.pixelSize: Fonts.bigger(FontUtils.sizeToPixels("large"))
            }

            TextField {
                id: smtpHostField
                width: parent.width
                placeholderText: hostField.text.length > 0
                               ? hostField.text
                               : "Sama kuin saapuva palvelin"
                text: page.smtpHostValue()
                font.pixelSize: Fonts.bigger(FontUtils.sizeToPixels("medium"))
            }

            Label {
                width: parent.width
                wrapMode: Text.WordWrap
                font.pixelSize: Fonts.bigger(FontUtils.sizeToPixels("small"))
                opacity: 0.7
                text: "Jätä tyhjäksi, jos käytät saapuvaa palvelinta, tai "
                      + "kirjoita toinen palvelin."
            }

            Label {
                text: "Yhteyden suojaus"
                font.pixelSize: Fonts.bigger(FontUtils.sizeToPixels("medium"))
            }

            OptionSelector {
                id: smtpSecuritySelector
                width: parent.width
                expanded: false
                model: ["SSL/TLS", "STARTTLS", "Ei salausta"]
                selectedIndex: {
                    var value = page.currentField("smtp_security", "ssl")
                    if (value === "starttls")
                        return 1
                    if (value === "plain")
                        return 2
                    return 0
                }
                onSelectedIndexChanged: page.resetSmtpPortIfStandard()
            }

            TextField {
                id: smtpPortField
                width: parent.width
                placeholderText: page.defaultSmtpPort(
                    smtpSecuritySelector.selectedIndex === 1 ? "starttls"
                    : smtpSecuritySelector.selectedIndex === 2 ? "plain"
                    : "ssl")
                text: page.currentField("smtp_port", "")
                inputMethodHints: Qt.ImhDigitsOnly
                font.pixelSize: Fonts.bigger(FontUtils.sizeToPixels("medium"))
            }

            Label {
                width: parent.width
                wrapMode: Text.WordWrap
                font.pixelSize: Fonts.bigger(FontUtils.sizeToPixels("small"))
                opacity: 0.7
                text: "Oletusportit: 465 (SSL/TLS), 587 (STARTTLS), "
                      + "25 (Ei salausta)."
            }

            Item {
                width: parent.width
                height: saveButton.height

                Button {
                    id: saveButton
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: "Tallenna ja päivitä"
                    color: theme.palette.normal.positive
                    font.pixelSize: Fonts.bigger(FontUtils.sizeToPixels("medium"))
                    enabled: hostField.text.length > 0
                             && userField.text.length > 0
                    onClicked: page.saveRequested(
                        hostField.text,
                        portField.text,
                        securitySelector.selectedIndex === 1 ? "starttls" : "ssl",
                        userField.text,
                        passwordField.text,
                        protocolSelector.selectedIndex === 1 ? "pop3" : "imap",
                        smtpHostField.text,
                        smtpPortField.text,
                        smtpSecuritySelector.selectedIndex === 1 ? "starttls"
                        : smtpSecuritySelector.selectedIndex === 2 ? "plain"
                        : "ssl")
                }
            }

            Label {
                width: parent.width
                wrapMode: Text.WordWrap
                font.pixelSize: Fonts.bigger(FontUtils.sizeToPixels("small"))
                opacity: 0.7
                text: "Asetukset ovat tämän sovelluksen omassa "
                      + "datakansiossa (tiedoston oikeudet 0600). "
                      + (page.config && page.config.password_location === "keyring"
                         ? "Salasana säilytetään järjestelmän avainrenkaassa. "
                         : "Salasana säilytetään tämän sovelluksen omassa "
                           + "tiedostossa. ")
                      + "Tilillä ei muuteta mitään eikä viestejä merkitä "
                      + "luetuiksi."
            }
        }
    }
}
