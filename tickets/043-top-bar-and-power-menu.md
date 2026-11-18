---
id: 043
title: Top bar and power menu like the phone remote
milestone: M7
depends_on: [028, 029, 030, 040]
---

## Goal

The remote's top bar and power menu look and work like the user's phone
remote's (the user, 2026-11-18: "the same in every way").

## Scope

- SPEC first.
- Top bar: a ☰ menu button on the left; the box's name as the title (Kodi's
  `System.FriendlyName`, else the config's `host`, until 042 gives boxes
  names) with a status line under it: **Connected** (green), **Offline**
  (red), **Connecting…**. The volume and "Nothing playing" leave the
  header; why Kodi can't be reached and the fix (036) stay, under the
  status.
- The ☰ menu: Kodi boxes (one for now; 042 fills it), Manage Kodi boxes
  (042), **Settings** (040's page moves here; the cog button goes), and
  the omakodi version at the bottom. Keyboard: a key opens it, arrows and
  Enter, Esc closes.
- Power menu, in the phone's order: **Wake up (Wake-on-LAN)**, **Turn on
  soundbar (HDMI-CEC)**, **Kodi power menu**, a divider, **Reboot**,
  **Shut down**. Always available, also while Kodi isn't answering (Wake
  up is how it comes back); the separate "Wake Kodi" button goes. Reboot
  and Shut down ask in a dialog "Reboot <box>?" with **Cancel** and
  **Reboot** (Shut down the same) instead of a second press.
- Kept (omakodi's extras, the user's choice): Reboot and Shut down only
  when Kodi allows them; `wakeOnLan: false` hides Wake up.

## Done when

- [x] Unit tests for the pure parts (menu items and order, the dialog's
      flow, the status words).
- [ ] Live, by the user: side by side with the phone, the top bar, menu
      and power menu match.
