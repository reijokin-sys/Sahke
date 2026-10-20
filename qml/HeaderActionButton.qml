/*
 * Sähke - mail client for Ubuntu Touch
 * Copyright (C) 2026 Reijo Kinnunen
 *
 * SPDX-License-Identifier: GPL-3.0-or-later
 */

import QtQuick 2.7
import Lomiri.Components 1.3

/*!
  The button an ActionBar draws an action with.

  The toolkit's own button gives the icon `units.gu(2)` and the theme's
  foreground colour. The header uses the theme's base surface, so the icon is
  slightly larger and uses the matching base text colour.
 */
AbstractButton {
    id: button

    height: parent ? parent.height : undefined
    implicitWidth: units.gu(4.4)
    activeFocusOnTab: true

    Rectangle {
        anchors.fill: parent
        color: button.pressed ? theme.palette.highlighted.background : "transparent"
    }

    Icon {
        anchors.centerIn: parent
        width: units.gu(2.5)
        height: width
        source: button.iconSource
        name: button.action && button.action.iconName ? button.action.iconName : ""
        color: theme.palette.normal.baseText
        opacity: button.enabled ? 1.0 : 0.4
    }
}
