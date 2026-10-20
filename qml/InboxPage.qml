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
import "i18n.js" as I18n

Page {
    id: page

    property string language: "en"
    property var messages
    property bool busy: false
    property bool configured: true
    property bool canLoadMore: false

    signal messageActivated(int index)
    signal messageTrashed(int index)
    signal refreshRequested()
    signal settingsRequested()
    signal loadMoreRequested()
    signal composeRequested()
    signal trashRequested()

    function tr(key) {
        return I18n.t(language, key)
    }

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
        title: page.tr("inbox.title")
        trailingActionBar.actions: [
            Action {
                iconName: "compose"
                text: page.tr("inbox.new")
                onTriggered: page.composeRequested()
            },
            Action {
                iconName: "settings"
                text: page.tr("inbox.settings")
                onTriggered: page.settingsRequested()
            },
            Action {
                iconName: "delete"
                text: page.tr("inbox.trash")
                onTriggered: page.trashRequested()
            },
            Action {
                iconName: "reload"
                text: page.tr("inbox.refresh")
                enabled: !page.busy
                onTriggered: page.refreshRequested()
            }
        ]
    }

    ActivityIndicator {
        anchors {
            top: parent.top
            topMargin: units.gu(1)
            horizontalCenter: parent.horizontalCenter
        }
        running: page.busy
        visible: running
        z: 2
    }

    ListView {
        id: listView
        // Page contents do not reserve room for the header, so the list is
        // anchored under it; otherwise the first row slides behind the
        // header and only its summary line stays visible.
        anchors {
            top: header.bottom
            left: parent.left
            right: parent.right
            bottom: parent.bottom
        }
        clip: true
        model: page.messages

        delegate: ListItem {
            id: entry
            height: layout.height + (divider.visible ? divider.height : 0)

            // A swipe to the right is the deletion gesture itself: once the
            // finger has travelled far enough the message moves into the
            // app's own trash, with no button to tap and no dialog. The red
            // wash grows under the finger as feedback. Moving a message into
            // the local trash is reversible, so the notice bar offers Undo.
            Rectangle {
                id: swipeFeedback
                anchors.fill: parent
                color: theme.palette.normal.negative
                opacity: Math.min(swipeArea.travel / (entry.width * 0.6), 0.45)
                visible: swipeArea.travel > 0 && !swipeArea.movedVertically

                Icon {
                    name: "delete"
                    color: "white"
                    width: units.gu(3)
                    height: width
                    anchors {
                        left: parent.left
                        leftMargin: units.gu(2)
                        verticalCenter: parent.verticalCenter
                    }
                }
            }

            ListItemLayout {
                id: layout
                title.text: model.subject && model.subject.length > 0
                            ? model.subject
                            : "(ei aihetta)"
                title.font.pixelSize: Fonts.bigger(FontUtils.sizeToPixels("medium"))
                // POP3 has no read state on the server, so there it is null
                // and the list simply does not emphasise anything.
                title.font.bold: model.seen === false
                subtitle.text: model.from
                subtitle.font.pixelSize: Fonts.bigger(FontUtils.sizeToPixels("small"))
                summary.text: page.dateLabel(model.date)
                summary.font.pixelSize: Fonts.bigger(FontUtils.sizeToPixels("x-small"))
            }

            // The drag target only records how far the finger travelled; the
            // row itself stays put and the red wash below is the feedback.
            Item {
                id: swipeProxy
                x: 0
                width: 0
                height: 0
            }

            MouseArea {
                id: swipeArea
                anchors.fill: parent
                // The list keeps the vertical gesture: a vertical drag steals
                // the press and scrolls as usual.
                preventStealing: false
                drag.target: swipeProxy
                drag.axis: Drag.XAxis
                drag.minimumX: 0
                drag.maximumX: entry.width

                property real startX: 0
                property real startY: 0
                property real travel: 0
                property bool tracking: false
                property bool movedVertically: false
                property bool moved: false

                onPressed: {
                    startX = mouse.x
                    startY = mouse.y
                    travel = 0
                    tracking = true
                    movedVertically = false
                    moved = false
                    swipeProxy.x = 0
                }

                onPositionChanged: {
                    if (!tracking)
                        return
                    var dx = mouse.x - startX
                    var dy = mouse.y - startY
                    if (Math.abs(dx) > units.gu(2)
                            || Math.abs(dy) > units.gu(2))
                        moved = true
                    // A mostly vertical move belongs to the list.
                    if (Math.abs(dy) > units.gu(2)
                            && Math.abs(dy) > Math.abs(dx)) {
                        tracking = false
                        movedVertically = true
                        travel = 0
                        swipeProxy.x = 0
                        return
                    }
                    travel = Math.max(0, swipeProxy.x)
                }

                onReleased: {
                    tracking = false
                    if (!movedVertically && travel >= units.gu(10)) {
                        travel = 0
                        swipeProxy.x = 0
                        page.messageTrashed(index)
                    } else {
                        travel = 0
                        swipeProxy.x = 0
                    }
                }

                onCanceled: {
                    tracking = false
                    travel = 0
                    swipeProxy.x = 0
                }

                onClicked: {
                    // A swipe that starts and ends on the row must not open
                    // the message as well.
                    if (moved)
                        return
                    page.messageActivated(index)
                }
            }
        }

        PullToRefresh {
            refreshing: page.busy
            onRefresh: page.refreshRequested()
            // Refresh is automatic after a delete and from the header
            // action, so the stock "Pull to refresh..." text only suggests
            // that a pull is required. Keep the manual pull gesture, but
            // show the spinner without the label.
            content: Item {}
        }

        footer: Item {
            width: listView.width
            height: page.canLoadMore ? units.gu(8) : 0
            visible: page.canLoadMore

            Button {
                anchors.centerIn: parent
                text: page.tr("inbox.showMore")
                enabled: !page.busy
                onClicked: page.loadMoreRequested()
            }
        }
    }

    Column {
        anchors {
            horizontalCenter: parent.horizontalCenter
            verticalCenter: listView.verticalCenter
        }
        width: Math.min(parent.width - units.gu(6), units.gu(34))
        spacing: units.gu(2)
        visible: listView.count === 0 && !page.busy

        Label {
            width: parent.width
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
            font.pixelSize: Fonts.bigger(FontUtils.sizeToPixels("medium"))
            text: page.configured
                  ? page.tr("inbox.empty")
                  : page.tr("inbox.unconfigured")
        }

        Item {
            width: parent.width
            height: button.height

            Button {
                id: button
                anchors.horizontalCenter: parent.horizontalCenter
                text: page.configured ? page.tr("inbox.refresh")
                                      : page.tr("inbox.openSettings")
                font.pixelSize: Fonts.bigger(FontUtils.sizeToPixels("medium"))
                onClicked: {
                    if (page.configured)
                        page.refreshRequested()
                    else
                        page.settingsRequested()
                }
            }
        }
    }
}
