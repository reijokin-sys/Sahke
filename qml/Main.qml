/*
 * Sähke - mail client for Ubuntu Touch
 * Copyright (C) 2026 Reijo Kinnunen
 *
 * SPDX-License-Identifier: GPL-3.0-or-later
 */

import QtQuick 2.7
import Lomiri.Components 1.3
import Lomiri.Components.Popups 1.3
import io.thp.pyotherside 1.5
import "fonts.js" as Fonts
import "theme.js" as Themejs
import "i18n.js" as I18n
import Qt.labs.settings 1.0

MainView {
    id: root
    objectName: "mainView"
    applicationName: "fi.reijo.sahkoposti"
    automaticOrientation: true
    anchorToKeyboard: true

    width: units.gu(50)
    height: units.gu(80)

    property bool busy: false
    property bool pythonReady: false
    property string language: "en"
    property bool configured: false
    // The theme the user chose: "punainen", "vihrea" or "sininen". Sähke has
    // its own three themes and does not follow the phone's.
    property string themeKey: "sininen"
    property var account: ({})
    // A short confirmation shown at the bottom ("Message sent.").
    property string notice: ""
    // True while the compose page is open, so "sent" knows what to close.
    property bool composing: false
    property int listLimit: 50
    property int shownCount: 0
    // The first config signal is the one read at start up; later ones mean
    // the settings were just saved.
    property bool configLoaded: false

    ListModel {
        id: messageModel
    }

    // The messages this app has deleted; they live in the app's own trash.
    ListModel {
        id: trashModel
    }

    // True while a message opened from the trash is on its way in, so the
    // message view can offer "Restore" instead of "Delete".
    property bool openingFromTrash: false
    // The message just swiped into the trash; the notice bar offers Undo.
    property string undoUid: ""

    function tr(key) {
        return I18n.t(language, key)
    }

    function setLanguage(code) {
        if (code !== "en" && code !== "fi")
            return
        root.language = code
        console.log("Sähke: language: " + code)
        if (root.pythonReady) {
            python.call("mail.set_language", [code], function (result) {
                if (result && result.ok)
                    root.language = result.result
            })
        }
    }

    function showError(message) {
        if (!message)
            return
        console.log("Sähke: error: " + message)
        PopupUtils.open(errorDialog, root, { text: String(message) })
    }

    function countText(count) {
        if (count === 1)
            return root.tr("count.one")
        return root.tr("count.many").replace("%1", count)
    }

    /// Set the toolkit theme to one of ours and keep it there. The modules
    /// travel inside the click, so the app looks the same on any phone.
    function applyTheme(key) {
        root.themeKey = key
        Theme.name = Themejs.moduleFor(key)
        console.log("Sähke: theme " + key + " -> " + Theme.name)
    }

    /// The user picked a theme in Settings: show it at once and remember it.
    function setTheme(key) {
        root.applyTheme(key)
        themeSettings.theme = key
    }

    function applyConfig(config) {
        root.account = config || ({})
        root.configured = root.account.configured === true
    }

    function fillModel(messages) {
        messageModel.clear()
        var list = messages || []
        for (var i = 0; i < list.length; i++) {
            var entry = list[i]
            messageModel.append({
                uid: entry.uid,
                from: entry.from,
                subject: entry.subject,
                date: entry.date,
                seen: entry.seen,
                snippet: entry.snippet,
                size: entry.size
            })
        }
        root.shownCount = messageModel.count
    }

    function fillTrash(messages) {
        trashModel.clear()
        var list = messages || []
        for (var i = 0; i < list.length; i++) {
            var entry = list[i]
            trashModel.append({
                uid: entry.uid,
                from: entry.from,
                subject: entry.subject,
                date: entry.date
            })
        }
    }

    function refresh() {
        if (!root.pythonReady)
            return
        root.busy = true
        python.call("mail.list_inbox", [root.listLimit], function (result) {
            root.busy = false
            if (result && result.ok === false)
                console.log("Sähke: list failed: " + result.error)
        })
    }

    function loadMore() {
        root.listLimit = root.listLimit + 50
        root.refresh()
    }

    function openMessage(uid, fromTrash) {
        if (!root.pythonReady)
            return
        root.openingFromTrash = fromTrash === true
        root.busy = true
        python.call("mail.fetch_message", [uid], function (result) {
            // The message itself arrives through the messageBody signal.
            if (result && result.ok === false) {
                root.openingFromTrash = false
                root.busy = false
            }
        })
    }

    function openTrash() {
        trashModel.clear()
        pageStack.push(trashPage)
        if (!root.pythonReady)
            return
        python.call("mail.list_trash", [], function (result) {
            if (result && result.ok)
                root.fillTrash(result.messages)
        })
    }

    function askDelete(message) {
        PopupUtils.open(deleteDialog, root, { message: message })
    }

    function entryAt(index) {
        if (index < 0 || index >= messageModel.count)
            return null
        var entry = messageModel.get(index)
        return {
            uid: entry.uid,
            from: entry.from,
            subject: entry.subject,
            date: entry.date,
            size: entry.size,
            seen: entry.seen
        }
    }

    // A swipe right on an inbox row lands here: no confirmation dialog,
    // because the message only moves into this app's own trash.
    function trashFromList(index) {
        var message = root.entryAt(index)
        if (!message)
            return
        // The row goes away at once; the refresh then makes the list match
        // the server again (and puts the row back if the write failed).
        messageModel.remove(index)
        root.shownCount = messageModel.count
        root.deleteMessage(message, true)
    }

    function deleteMessage(message, offerUndo) {
        if (!root.pythonReady || !message)
            return
        root.busy = true
        // Only what the trash list needs; the body stays on the server.
        python.call("mail.delete_message", [{
            uid: message.uid,
            from: message.from,
            subject: message.subject,
            date: message.date,
            size: message.size,
            seen: message.seen
        }], function (result) {
            root.busy = false
            if (result && result.ok) {
                if (pageStack.depth > 1)
                    pageStack.pop()
                root.notice = root.tr("notice.trashed")
                root.undoUid = offerUndo === true ? String(message.uid) : ""
                noticeTimer.restart()
                root.refresh()
            }
        })
    }

    function undoTrash() {
        if (!root.pythonReady || root.undoUid.length === 0)
            return
        var uid = root.undoUid
        root.undoUid = ""
        root.busy = true
        python.call("mail.restore_message", [uid], function (result) {
            root.busy = false
            if (result && result.ok) {
                root.notice = root.tr("notice.restored")
                noticeTimer.restart()
                root.refresh()
            }
        })
    }

    function restoreMessage(uid) {
        if (!root.pythonReady)
            return
        root.busy = true
        python.call("mail.restore_message", [uid], function (result) {
            root.busy = false
            if (result && result.ok) {
                // Back to the trash list, which is now one shorter.
                if (pageStack.depth > 1)
                    pageStack.pop()
                if (result.messages)
                    root.fillTrash(result.messages)
                root.notice = root.tr("notice.restored")
                noticeTimer.restart()
                root.refresh()
            }
        })
    }

    function askEmptyTrash() {
        PopupUtils.open(emptyTrashDialog, root, { count: trashModel.count })
    }

    function askLogout() {
        PopupUtils.open(logoutDialog, root)
    }

    function logout() {
        if (!root.pythonReady)
            return
        root.busy = true
        python.call("mail.logout", [], function (result) {
            root.busy = false
            if (result && result.ok) {
                messageModel.clear()
                trashModel.clear()
                root.listLimit = 50
                root.shownCount = 0
                root.applyConfig({})
                if (pageStack.depth > 1)
                    pageStack.pop()
                root.notice = root.tr("notice.signedOut")
                noticeTimer.restart()
            }
        })
    }

    // The one action in this app that changes the mailbox: it is asked for
    // separately, and the dialog says what it cannot undo.
    function emptyTrash() {
        if (!root.pythonReady)
            return
        root.busy = true
        python.call("mail.empty_trash", [], function (result) {
            root.busy = false
            if (result && result.ok) {
                if (result.messages)
                    root.fillTrash(result.messages)
                root.notice = (result.deleted && result.deleted.length > 0)
                              ? root.tr("notice.deleted").replace(
                                    "%1", root.countText(result.deleted.length))
                              : root.tr("notice.trashAlreadyEmpty")
                noticeTimer.restart()
                root.refresh()
            }
        })
    }

    function saveSettings(host, port, security, username, password, protocol,
                          smtpHost, smtpPort, smtpSecurity) {
        if (!root.pythonReady)
            return
        root.busy = true
        python.call("mail.configure",
                    [host, port, security, username, password, protocol,
                     smtpHost, smtpPort, smtpSecurity],
                    function (result) {
            root.busy = false
            if (result && result.ok) {
                root.listLimit = 50
                pageStack.pop()
            }
        })
    }

    function openCompose(to, subject, body, replyTo) {
        root.composing = true
        pageStack.push(composePage, {
            to: to, subject: subject, body: body, replyTo: replyTo
        })
    }

    // Answer the message that is open: the address, "Re:" and the Message-ID
    // that keeps the thread together in the other mail client.
    function replyToMessage(message) {
        if (!message)
            return
        var subject = message.subject ? String(message.subject) : ""
        var lower = subject.substring(0, 5).toLowerCase()
        if (lower.indexOf("re:") !== 0 && lower.indexOf("vast:") !== 0)
            subject = root.tr("reply.prefix") + subject
        root.openCompose(message.from ? String(message.from) : "", subject, "",
                         message.message_id ? String(message.message_id) : "")
    }

    function sendMessage(to, subject, body, replyTo) {
        if (!root.pythonReady)
            return
        python.call("mail.send_message", [to, subject, body, replyTo],
                    function (result) {})
    }

    Python {
        id: python

        Component.onCompleted: {
            // mail.py sits in the root of the click package, one level up.
            addImportPath(Qt.resolvedUrl("../"))
            importModule("mail", function () {
                root.pythonReady = true
                python.call("mail.language", [], function (result) {
                    if (result && result.ok && result.result)
                        root.language = result.result
                    console.log("Sähke: language: " + root.language)
                    python.call("mail.load_config", [], function () {})
                })
            })
        }

        onError: {
            console.log("Sähke: Python error: " + traceback)
            root.showError(String(traceback).split("\n").pop())
        }

        // PyOtherSide delivers pyotherside.send(name, ...) as one list:
        // ["name", argument, ...].
        onReceived: {
            if (!data || data.length === 0)
                return
            var name = data[0]
            var value = data.length > 1 ? data[1] : undefined
            if (name === "busy") {
                root.busy = (value === true)
            } else if (name === "error") {
                root.showError(value)
            } else if (name === "config") {
                root.applyConfig(value)
                if (!root.configLoaded) {
                    root.configLoaded = true
                    // Do not shout about a missing account on the first run;
                    // the inbox page already says it needs settings.
                    if (!root.configured)
                        return
                }
                root.refresh()
            } else if (name === "credentials") {
                // The journal then shows where the password lives - and
                // whether the sandbox let the keyring be used at all.
                console.log("Sähke: password location: " + value)
            } else if (name === "messageList") {
                root.fillModel(value)
            } else if (name === "messageBody") {
                pageStack.push(messagePage, {
                    message: value,
                    inTrash: root.openingFromTrash
                })
                root.openingFromTrash = false
            } else if (name === "trashList") {
                root.fillTrash(value)
            } else if (name === "sent") {
                if (root.composing) {
                    root.composing = false
                    pageStack.pop()
                }
                root.notice = root.tr("notice.sent")
                noticeTimer.restart()
            }
        }
    }

    /// The theme must be the user's own before the first page is drawn, or
    /// the first frame would flash the phone's theme. This object reads and
    /// writes the choice without a second process.
    Settings {
        id: themeSettings
        fileName: "/home/phablet/.config/fi.reijo.sahkoposti/theme.conf"
        property string theme: "sininen"
    }

    QtObject {
        id: themeChoice
        Component.onCompleted: root.applyTheme(themeSettings.theme)
    }

    Connections {
        target: Theme
        ignoreUnknownSignals: true
        // Nothing else may take the theme from us - not the shell's light/dark
        // logic, not a toolkit reload. If something changes it, put the
        // user's choice back.
        function onNameChanged() {
            var wanted = Themejs.moduleFor(root.themeKey)
            if (Theme.name !== wanted)
                Theme.name = wanted
        }
    }

    PageStack {
        id: pageStack
        anchors.fill: parent

        Component.onCompleted: push(inboxPage)
    }

    Component {
        id: inboxPage
        InboxPage {
            language: root.language
            messages: messageModel
            busy: root.busy
            configured: root.configured
            canLoadMore: root.shownCount >= root.listLimit

            onMessageActivated: root.openMessage(messageModel.get(index).uid)
            onMessageTrashed: root.trashFromList(index)
            onRefreshRequested: root.refresh()
            onSettingsRequested: pageStack.push(settingsPage, { config: root.account })
            onLoadMoreRequested: root.loadMore()
            onComposeRequested: root.openCompose("", "", "", "")
            onTrashRequested: root.openTrash()
        }
    }

    Component {
        id: messagePage
        MessagePage {
            language: root.language
            onReplyRequested: root.replyToMessage(message)
            onDeleteRequested: root.askDelete(message)
            onRestoreRequested: root.restoreMessage(message.uid)
        }
    }

    Component {
        id: trashPage
        TrashPage {
            language: root.language
            messages: trashModel
            onMessageActivated: root.openMessage(trashModel.get(index).uid, true)
            onEmptyRequested: root.askEmptyTrash()
        }
    }

    Component {
        id: composePage
        ComposePage {
            language: root.language
            busy: root.busy
            onSendRequested: root.sendMessage(to, subject, body, replyTo)
        }
    }

    Component {
        id: settingsPage
        SettingsPage {
            language: root.language
            themeKey: root.themeKey
            onLanguageRequested: root.setLanguage(code)
            onThemeRequested: root.setTheme(key)
            onLogoutRequested: root.askLogout()
            onSaveRequested: root.saveSettings(host, port, security, username,
                                               password, protocol, smtpHost,
                                               smtpPort, smtpSecurity)
        }
    }

    Component {
        id: errorDialog
            Dialog {
                id: dialog
                title: root.tr("app.title")

                Button {
                    text: root.tr("dialog.close")
                    color: theme.palette.normal.positive
                    font.pixelSize: Fonts.bigger(FontUtils.sizeToPixels("medium"))
                    onClicked: PopupUtils.close(dialog)
            }
        }
    }

    Component {
        id: deleteDialog
        Dialog {
            id: dialog
            property var message: ({})
            title: root.tr("dialog.delete.title")
            text: root.tr("dialog.delete.text")

            Button {
                text: root.tr("dialog.delete.cancel")
                font.pixelSize: Fonts.bigger(FontUtils.sizeToPixels("medium"))
                onClicked: PopupUtils.close(dialog)
            }
            Button {
                text: root.tr("dialog.delete.confirm")
                color: theme.palette.normal.negative
                font.pixelSize: Fonts.bigger(FontUtils.sizeToPixels("medium"))
                onClicked: {
                    PopupUtils.close(dialog)
                    root.deleteMessage(dialog.message)
                }
            }
        }
    }

    Component {
        id: emptyTrashDialog
        Dialog {
            id: dialog
            property int count: 0
            title: root.tr("dialog.empty.title")
            text: root.tr("dialog.empty.text").replace("%1",
                                                       root.countText(count))

            Button {
                text: root.tr("dialog.empty.cancel")
                font.pixelSize: Fonts.bigger(FontUtils.sizeToPixels("medium"))
                onClicked: PopupUtils.close(dialog)
            }
            Button {
                text: root.tr("dialog.empty.confirm")
                color: theme.palette.normal.negative
                font.pixelSize: Fonts.bigger(FontUtils.sizeToPixels("medium"))
                onClicked: {
                    PopupUtils.close(dialog)
                    root.emptyTrash()
                }
            }
        }
    }

    Component {
        id: logoutDialog
        Dialog {
            id: dialog
            title: root.tr("dialog.logout.title")
            text: root.tr("dialog.logout.text")

            Button {
                text: root.tr("dialog.logout.cancel")
                font.pixelSize: Fonts.bigger(FontUtils.sizeToPixels("medium"))
                onClicked: PopupUtils.close(dialog)
            }
            Button {
                text: root.tr("dialog.logout.confirm")
                color: theme.palette.normal.negative
                font.pixelSize: Fonts.bigger(FontUtils.sizeToPixels("medium"))
                onClicked: {
                    PopupUtils.close(dialog)
                    root.logout()
                }
            }
        }
    }

    Rectangle {
        id: noticeBar
        anchors {
            left: parent.left
            right: parent.right
            bottom: parent.bottom
        }
        height: units.gu(5)
        color: theme.palette.normal.positive
        visible: root.notice.length > 0
        z: 3

        Row {
            anchors.centerIn: parent
            spacing: units.gu(2)

            Label {
                anchors.verticalCenter: parent.verticalCenter
                text: root.notice
                color: "white"
                font.pixelSize: Fonts.bigger(FontUtils.sizeToPixels("medium"))
            }

            Button {
                anchors.verticalCenter: parent.verticalCenter
                text: root.tr("common.undo")
                visible: root.undoUid.length > 0
                color: "white"
                font.pixelSize: Fonts.bigger(FontUtils.sizeToPixels("medium"))
                onClicked: root.undoTrash()
            }
        }
    }

    Timer {
        id: noticeTimer
        interval: 4000
        onTriggered: {
            root.notice = ""
            root.undoUid = ""
        }
    }
}
