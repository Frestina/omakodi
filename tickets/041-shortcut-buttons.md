---
id: 041
title: Shortcut buttons
milestone: M6
depends_on: [035]
---

## Goal

A few buttons in the remote that open a place in Kodi in one press:
Movies, TV shows and Music by default, each changeable to any of Kodi's
screens, library sections, add-ons (and their folders), favourites or
sources, with Kodi's own artwork as the icon.

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

- [ ] Unit tests with the fake Kodi: listing, picking, opening, keeping
      the choice.
- [ ] Live, by the user: the defaults open Movies, TV shows and Music;
      one changed to an add-on folder opens it.
