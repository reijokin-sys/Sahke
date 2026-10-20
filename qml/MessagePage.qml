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

    property var message: ({})
    // True when the message was opened from the trash, where the action is
    // "put it back" instead of "delete".
    property bool inTrash: false

    signal replyRequested()
    signal deleteRequested()
    signal restoreRequested()

    function dateLabel(iso) {
        if (!iso)
            return ""
        var when = new Date(iso)
        if (isNaN(when.getTime()))
            return String(iso)
        return Qt.formatDateTime(when, "d.M.yyyy HH:mm")
    }

    // Declared as objects of their own, because QML cannot parse a ternary
    // between two inline lists of objects (the phone caught that).
    Action {
        id: replyAction
        iconName: "mail-reply"
        text: "Vastaa"
        onTriggered: page.replyRequested()
    }

    Action {
        id: deleteAction
        iconName: "delete"
        text: "Poista"
        onTriggered: page.deleteRequested()
    }

    Action {
        id: restoreAction
        iconName: "undo"
        text: "Palauta"
        onTriggered: page.restoreRequested()
    }

    header: SahkopostiHeader {
        id: header
        title: page.message.subject && page.message.subject.length > 0
               ? page.message.subject
               : "(ei aihetta)"
        // In the trash the only action is "put it back".
        trailingActionBar.actions: page.inTrash
                                   ? [restoreAction]
                                   : [replyAction, deleteAction]
    }

    function detail(label, value) {
        return value && value.length > 0 ? label + ": " + value : ""
    }

    Flickable {
        id: messageFlickable
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
                width: parent.width
                text: page.message.subject && page.message.subject.length > 0
                      ? page.message.subject
                      : "(ei aihetta)"
                font.pixelSize: Fonts.bigger(FontUtils.sizeToPixels("large"))
                wrapMode: Text.WordWrap
            }

            Label {
                width: parent.width
                text: page.detail("Lähettäjä", page.message.from)
                wrapMode: Text.WordWrap
                font.pixelSize: Fonts.bigger(FontUtils.sizeToPixels("medium"))
            }

            Label {
                width: parent.width
                visible: text.length > 0
                text: page.detail("Vastaanottaja", page.message.to)
                wrapMode: Text.WordWrap
                font.pixelSize: Fonts.bigger(FontUtils.sizeToPixels("medium"))
            }

            Label {
                width: parent.width
                visible: text.length > 0
                text: page.detail("Kopio", page.message.cc)
                wrapMode: Text.WordWrap
                font.pixelSize: Fonts.bigger(FontUtils.sizeToPixels("medium"))
            }

            Label {
                width: parent.width
                text: page.detail("Päiväys", page.dateLabel(page.message.date))
                wrapMode: Text.WordWrap
                font.pixelSize: Fonts.bigger(FontUtils.sizeToPixels("medium"))
            }

            Rectangle {
                width: parent.width
                height: units.dp(1)
                color: theme.palette.normal.base
            }

            Label {
                width: parent.width
                wrapMode: Text.WordWrap
                textFormat: Text.PlainText
                text: page.message.text && page.message.text.length > 0
                      ? page.message.text
                      : "(Tässä viestissä ei ole luettavaa tekstiosaa.)"
                font.pixelSize: Fonts.message(FontUtils.sizeToPixels("medium"))
            }

            Label {
                width: parent.width
                // A real boolean: without a message the old form handed
                // `undefined` to `visible` (the phone's qmlscene check).
                visible: (page.message.attachments || []).length > 0
                wrapMode: Text.WordWrap
                text: page.message.attachments
                      ? "Liitteet: " + page.message.attachments.join(", ")
                      : ""
                font.pixelSize: Fonts.bigger(FontUtils.sizeToPixels("small"))
            }
        }
    }
}
