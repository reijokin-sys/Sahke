/*
 * Sähke - mail client for Ubuntu Touch
 * Copyright (C) 2026 Reijo Kinnunen
 *
 * SPDX-License-Identifier: GPL-3.0-or-later
 */

import QtQuick 2.7
import Lomiri.Components 1.3

/*!
  The app's header: the toolkit's PageHeader with the selected theme's colours.
  The background is the theme's base surface and its title, back arrow and
  action icons use the matching text colour.

  The action-button delegate is set here so every page gets the bigger green
  icons without repeating the component.
 */
PageHeader {
    id: header

    StyleHints {
        backgroundColor: theme.palette.normal.base
        foregroundColor: theme.palette.normal.baseText
        dividerColor: theme.palette.normal.base
    }

    Component {
        id: headerActionDelegate

        HeaderActionButton {
            action: modelData
        }
    }

    leadingActionBar.delegate: headerActionDelegate
    trailingActionBar.delegate: headerActionDelegate
}
