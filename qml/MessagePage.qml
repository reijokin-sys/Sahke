/*
 * Sähke - mail client for Ubuntu Touch
 * Copyright (C) 2026 Reijo Kinnunen
 *
 * SPDX-License-Identifier: GPL-3.0-or-later
 */

import QtQuick 2.7
import Lomiri.Components 1.3
import "fonts.js" as Fonts
import "i18n.js" as I18n

Page {
    id: page

    property string language: "en"
    property var message: ({})
    // True when the message was opened from the trash, where the action is
    // "put it back" instead of "delete".
    property bool inTrash: false

    signal replyRequested()
    signal deleteRequested()
    signal restoreRequested()

    function tr(key) {
        return I18n.t(language, key)
    }

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
        text: page.tr("message.reply")
        onTriggered: page.replyRequested()
    }

    Action {
        id: deleteAction
        iconName: "delete"
        text: page.tr("message.delete")
        onTriggered: page.deleteRequested()
    }

    Action {
        id: restoreAction
        iconName: "undo"
        text: page.tr("message.restore")
        onTriggered: page.restoreRequested()
    }

    header: SahkopostiHeader {
        id: header
        title: page.message.subject && page.message.subject.length > 0
               ? page.message.subject
               : page.tr("message.noSubject")
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
                      : page.tr("message.noSubject")
                font.pixelSize: Fonts.bigger(FontUtils.sizeToPixels("large"))
                wrapMode: Text.WordWrap
            }

            Label {
                width: parent.width
                text: page.detail(page.tr("message.from"), page.message.from)
                wrapMode: Text.WordWrap
                font.pixelSize: Fonts.bigger(FontUtils.sizeToPixels("medium"))
            }

            Label {
                width: parent.width
                visible: text.length > 0
                text: page.detail(page.tr("message.to"), page.message.to)
                wrapMode: Text.WordWrap
                font.pixelSize: Fonts.bigger(FontUtils.sizeToPixels("medium"))
            }

            Label {
                width: parent.width
                visible: text.length > 0
                text: page.detail(page.tr("message.cc"), page.message.cc)
                wrapMode: Text.WordWrap
                font.pixelSize: Fonts.bigger(FontUtils.sizeToPixels("medium"))
            }

            Label {
                width: parent.width
                text: page.detail(page.tr("message.date"),
                                  page.dateLabel(page.message.date))
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
                      : page.tr("message.noText")
                font.pixelSize: Fonts.message(FontUtils.sizeToPixels("medium"))
            }

            Label {
                width: parent.width
                // A real boolean: without a message the old form handed
                // `undefined` to `visible` (the phone's qmlscene check).
                visible: (page.message.attachments || []).length > 0
                wrapMode: Text.WordWrap
                text: page.message.attachments
                      ? page.tr("message.attachments")
                        + page.message.attachments.join(", ")
                      : ""
                font.pixelSize: Fonts.bigger(FontUtils.sizeToPixels("small"))
            }
        }
    }
}
