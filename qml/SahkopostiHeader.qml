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
  The app's header: the toolkit's PageHeader with Sähke's own colours.

  The background is the brand lilac and the title, back arrow and action
  icons are the brand green, in both themes. This is the same header
  treatment Puhuri uses; the colours are the app's identity, not part of the
  selectable theme.

  The action-button delegate is set here so every page gets the bigger green
  icons without repeating the component.
 */
PageHeader {
    id: header

    StyleHints {
        backgroundColor: Themejs.BRAND_LILAC
        foregroundColor: Themejs.BRAND_GREEN
        dividerColor: Themejs.BRAND_LILAC
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
