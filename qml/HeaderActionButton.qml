/*
 * Sähke - mail client for Ubuntu Touch
 * Copyright (C) 2026 Reijo Kinnunen
 *
 * SPDX-License-Identifier: GPL-3.0-or-later
 */

import QtQuick 2.7
import Lomiri.Components 1.3
import "theme.js" as Themejs

/*!
  The button an ActionBar draws an action with.

  The toolkit's own button gives the icon `units.gu(2)` and the theme's
  foreground colour. The header has Sähke's lilac background in both
  themes, so the icon is the brand green and slightly larger, the same way
  Puhuri's header buttons are.
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
        color: Themejs.BRAND_GREEN
        opacity: button.enabled ? 1.0 : 0.4
    }
}
