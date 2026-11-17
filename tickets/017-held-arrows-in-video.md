---
id: 017
title: A held arrow skips once during a video
milestone: M2
depends_on: [007, 010]
---

## Goal

Holding an arrow while a video plays full screen skips once, like one press
(SPEC "Remote panel", "Daemon protocol"). In Kodi's menus, a held arrow still
scrolls.

Found in the ticket 012 live check: holding Right for about a second at the
start of a 20 minute video skipped to its end. During plain fullscreen video
the arrows are `stepforward`/`stepback` (about 10 s) and
`chapterorbigstepforward`/`back` (about 60 s), and the keyboard repeats 10 to
25 times a second. On a fast network Kodi answers each key at once, so the
"wait for the previous answer" rule lets nearly every repeat through.

## Scope

- The remote marks a key repeat: `{"cmd": "control", "action": "right",
  "repeat": true}` (from `event.isAutoRepeat`; the service passes it on).
- The daemon drops a repeat of `up` `down` `left` `right` during plain
  fullscreen video (the check `control.py` already makes, cached briefly).
  The result is `ok` with an empty message, so the remote shows nothing.
- Repeats outside plain fullscreen video, and every first press, behave as
  now. `repeat` on other actions is ignored.
- A missing or non-boolean `repeat` counts as false.

## Done when

- [ ] Unit tests against the fake: a repeated `right` during plain fullscreen
      video makes no Kodi call; a first press does; a repeated `down` in a
      menu does; `repeat` on `select` is ignored.
- [ ] Live, with the user's go-ahead: holding Right for a second during a
      video skips once; holding Down in a list scrolls.
