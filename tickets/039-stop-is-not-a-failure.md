---
id: 039
title: A stop you send isn't a YouTube failure
milestone: M6
depends_on: [005]
---

## Goal

Stopping a YouTube video while its verdict is pending (`x` in the remote,
`omakodi control stop`, within 30 s of `play`) reads as a failure today:
omakodi opens it again with SendToKodi, and `smart` mode avoids the
YouTube add-on for 30 minutes. A stop the user sent should end the watch
without a fallback.

## Scope

- SPEC first.
- The verdict can run in the daemon or in a separate `omakodi play`
  process (the keybinding), while the stop comes from the remote's daemon
  or the terminal: so a `stop` through omakodi notes its time in
  `~/.local/state/omakodi/` and the verdict reads it. A `Player.OnStop`
  after a stop omakodi sent since the play began is "stopped": no
  fallback, no `smart` record, the message says it was stopped.
- A stop from Kodi's own remote can't be told apart from a failure; the
  README's known limits say so.

## Done when

- [x] Unit tests: a stop sent during the verdict (same process and another
      process) gives "stopped"; a stop before the play began doesn't count;
      a failure still falls back.
      *Also during the SendToKodi watch (038).*
- [x] Live, by the user: play a YouTube link, press `x` within a few
      seconds: it stays stopped, no SendToKodi. *2026-11-18: the user:
      "it works".*
