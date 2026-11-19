---
id: 041
title: Shortcut buttons
milestone: M6
depends_on: [035]
---

## Goal

A strip of five buttons under the top bar, as on the user's phone remote:
**Home, Movies, TV shows, Music, Send a link** by default, each
changeable to any of Kodi's screens, library sections, add-ons (and their
folders), favourites or sources, or to Send a link, with Kodi's own
artwork as the icon.

## Widened (2026-11-18, the comparison with the phone remote)

- All five slots can be changed (a long press with the mouse, or a key):
  **Choose from Kodi…**, a typed Kodi path or add-on
  (`plugin://plugin.video.youtube`), **Use "Send a link"**, **Change
  icon** (Kodi's artwork, or one of about 70 built-in icons), **Reset**,
  Save, Cancel. Kept per box.
- **Send a link** opens a dialog: a text field ("YouTube, X, Rumble, …
  link"), Paste and Clear, and **Play** / **Queue** (enabled once it
  holds a link) and **Cancel**. The Play link / Queue link buttons go;
  `p` and `q` keep reading the clipboard.
- The picker: a list per level with a back arrow, "Use this folder",
  "Loading from Kodi…", "No folders here", "Couldn't load" with **Try
  again**.

## Scope

- SPEC first: where the row sits (the remote must still fit an 800 px
  screen), keys for the buttons, how one is changed (a picker in the
  remote, keyboard first), where the choice is kept (per box, not secret:
  `~/.local/state/omakodi/` or the widget settings).
- The picker lists what Kodi has, live: `GUI.ActivateWindow` windows,
  `Files.GetDirectory` for library sections and add-on folders,
  `Addons.GetAddons`, `Favourites.GetFavourites`, `Files.GetSources`.
- Opening one: `GUI.ActivateWindow` with the window and path.
- Artwork through the existing art cache; a plain icon without art.

## Done when

- [x] Unit tests with the fake Kodi: listing, picking, opening, keeping
      the choice.
- [x] Live, by the user: the defaults open Movies, TV shows and Music;
      one changed to an add-on folder opens it. *2026-11-19: the user's
      check passes.*
