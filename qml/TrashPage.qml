/*
 * Sähke - mail client for Ubuntu Touch
 * Copyright (C) 2026 Reijo Kinnunen
 *
 * SPDX-License-Identifier: GPL-3.0-or-later
 */

import QtQuick 2.7
import Lomiri.Components 1.3
import Lomiri.Components.ListItems 1.3
import "fonts.js" as Fonts

Page {
    id: page

    // The messages this app has deleted. They are still in the mailbox.
    property var messages

    signal messageActivated(int index)
    signal emptyRequested()

    function dateLabel(iso) {
        if (!iso)
            return ""
        var when = new Date(iso)
        if (isNaN(when.getTime()))
            return ""
        return Qt.formatDateTime(when, "d.M.yyyy HH:mm")
    }

    header: SahkopostiHeader {
        id: header
        title: "Roskakori"
        trailingActionBar.actions: [
            Action {
                iconName: "delete"
                text: "Tyhjennä roskakori"
                // A real boolean: before the list arrives `messages` is
                // undefined, and the old form handed that to `enabled`.
                enabled: (page.messages ? page.messages.count : 0) > 0
                onTriggered: page.emptyRequested()
            }
        ]
    }

    ListView {
        id: listView
        anchors {
            top: header.bottom
            left: parent.left
            right: parent.right
            bottom: hint.top
        }
        clip: true
        model: page.messages

        delegate: ListItem {
            id: entry
            height: layout.height + (divider.visible ? divider.height : 0)

            ListItemLayout {
                id: layout
                title.text: model.subject && model.subject.length > 0
                            ? model.subject
                            : "(ei aihetta)"
                title.font.pixelSize: Fonts.bigger(FontUtils.sizeToPixels("medium"))
                subtitle.text: model.from
                subtitle.font.pixelSize: Fonts.bigger(FontUtils.sizeToPixels("small"))
                summary.text: page.dateLabel(model.date)
                summary.font.pixelSize: Fonts.bigger(FontUtils.sizeToPixels("x-small"))
            }

            onClicked: page.messageActivated(index)
        }

        Label {
            anchors.centerIn: parent
            width: parent.width - units.gu(6)
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
            visible: listView.count === 0
            opacity: 0.7
            font.pixelSize: Fonts.bigger(FontUtils.sizeToPixels("medium"))
            text: "Roskakori on tyhjä."
        }
    }

    Label {
        id: hint
        anchors {
            left: parent.left
            right: parent.right
            bottom: parent.bottom
            margins: units.gu(2)
        }
        height: paintedHeight + units.gu(1)
        wrapMode: Text.WordWrap
        font.pixelSize: Fonts.bigger(FontUtils.sizeToPixels("small"))
        opacity: 0.7
        text: "Nämä viestit on vain piilotettu tässä sovelluksessa - "
              + "postilaatikkoa ei muuteta. Avaa viesti palauttaaksesi sen."
    }
}
