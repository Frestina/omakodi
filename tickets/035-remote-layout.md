---
id: 035
title: The remote's layout, keys grouped by what they do
milestone: M5
depends_on: [023, 025, 026, 033]
---

## Goal

The remote laid out like a phone remote (the user's wish, 2026-11-18):
links, volume, actions and a big D-pad, with now playing as a bar at the
bottom that opens into the seek bar, transport, details and queue, and
the poster blurred behind it all.

## Scope

- SPEC first ("Remote panel": the layout list).
- Panel only: the daemon, service and protocol don't change. Every key
  and action stays; only where the buttons sit and how they look.
- Fits on a screen 800 px tall with a list open.
- `n` shows more or less of what plays.

## Done when

- [x] `tests/run` passes; the new key is in RemoteKeys.js with a test.
- [x] Live, by the user: the layout looks right on the laptop, the keys
      and buttons still do what they did, the blurred poster shows behind
      a video with art. *2026-11-18: screenshots on the laptop first (two
      shell crashes found and fixed, then six opens without one); then
      the user: "it works".*
