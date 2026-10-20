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

    property string to: ""
    property string subject: ""
    property string body: ""
    // The Message-ID this message answers, when it is a reply.
    property string replyTo: ""
    property bool busy: false
    property bool canSend: !busy && toField.text.trim().length > 0

    signal sendRequested(string to, string subject, string body, string replyTo)

    header: SahkopostiHeader {
        id: header
        title: page.replyTo.length > 0 ? "Vastaa" : "Uusi viesti"
    }

    Flickable {
        id: composeFlickable
        anchors {
            top: header.bottom
            left: parent.left
            right: parent.right
            bottom: parent.bottom
        }
        clip: true
        contentWidth: parent.width
        contentHeight: column.height + units.gu(4)

        Column {
            id: column
            x: units.gu(2)
            y: units.gu(2)
            width: parent.width - units.gu(4)
            spacing: units.gu(1)

            Label {
                text: "Vastaanottaja"
                font.pixelSize: Fonts.bigger(FontUtils.sizeToPixels("medium"))
            }
            TextField {
                id: toField
                width: parent.width
                text: page.to
                placeholderText: "nimi@esimerkki.fi"
                inputMethodHints: Qt.ImhEmailCharactersOnly | Qt.ImhNoAutoUppercase
                font.pixelSize: Fonts.bigger(FontUtils.sizeToPixels("medium"))
            }

            Label {
                text: "Aihe"
                font.pixelSize: Fonts.bigger(FontUtils.sizeToPixels("medium"))
            }
            TextField {
                id: subjectField
                width: parent.width
                text: page.subject
                font.pixelSize: Fonts.bigger(FontUtils.sizeToPixels("medium"))
            }

            Label {
                text: "Viesti"
                font.pixelSize: Fonts.bigger(FontUtils.sizeToPixels("medium"))
            }
            TextArea {
                id: bodyField
                width: parent.width
                height: units.gu(16)
                text: page.body
                font.pixelSize: Fonts.message(FontUtils.sizeToPixels("medium"))
            }

            Button {
                width: parent.width
                text: page.busy ? "Lähetetään…" : "Lähetä"
                color: theme.palette.normal.positive
                font.pixelSize: Fonts.bigger(FontUtils.sizeToPixels("medium"))
                enabled: page.canSend
                onClicked: page.sendRequested(toField.text.trim(),
                                              subjectField.text,
                                              bodyField.text,
                                              page.replyTo)
            }

            Label {
                width: parent.width
                visible: page.busy
                text: "Yhdistetään lähettävään palvelimeen…"
                font.pixelSize: Fonts.bigger(FontUtils.sizeToPixels("small"))
                wrapMode: Text.WordWrap
            }
        }
    }
}
