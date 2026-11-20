---
id: 061
title: Show the remote off in the README
milestone: M8
depends_on: [041–060]
---

## Goal

The README opens with a picture of the remote and a short animation of it
in use, so someone browsing the repo sees what they get. `preview.png`
(the marketplace screenshot) shows today's remote. The user (2026-11-20):
"make a gif/image or video in the readme … showing it off".

## Scope

- With the fake Kodi and fictional data only (the demo from 013, the
  omarchy-plugin-demo skill): made-up titles, posters, plots, box name
  (`kodi.example.lan`). Nothing from the user's box, screen or accounts
  in any frame (no real bar contents, notifications or wallpaper that
  identify the user; crop to the remote).
- `preview.png` retaken: the remote with something playing, the strip
  of five, the action row.
- An animation of 10–20 s, small enough for a README (aim under 3 MB):
  e.g. the remote opening, arrows moving, the now-playing page, Details
  with colours and links, the queue, closing. A GIF, or a looping video
  GitHub plays inline, whichever looks better at that size.
- The README shows both near the top, with alt text.
- The scripts that make them live in `demo/`, so they can be made again.
- No live tests on the user's TV.

## Done when

- [x] `demo/` makes the screenshot and the animation from the fake Kodi
      in one command; `tests/run` passes. *2026-11-20: `demo/run -- demo/capture`
      (was `demo/screenshot`): the shell restarted against the fake with
      throwaway XDG_STATE_HOME and XDG_CACHE_HOME (the real config and state
      untouched, checked), `preview.png` (672x980, the card only) and
      `docs/remote.gif` (480x700, 17.9 s, 1.0 MB, 15 fps; the D-pad, now
      playing, Details, queue, faded in and out in the card's colour), keys
      typed only while the daemon was on the fake (it got Up, Right, Down,
      Select); shell, workspace and pointer put back; 451 tests pass.*
- [x] Every frame checked by eye for anything real. *Every third GIF frame
      and the preview: only the card, box `kodi.example.lan`, the made-up
      film, poster, plot (example.org link) and queue. The now-playing
      page's "ends HH:MM" is the clock at capture time.*
- [ ] Live, by the user: the README's picture and animation look right.
