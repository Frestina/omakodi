---
id: 020
title: Next and previous in the queue
milestone: M2
depends_on: [007, 008, 010]
---

## Goal

With a few videos queued, skip to the next one (or back to the previous one)
from the remote, the terminal and IPC (SPEC "Remote commands", "Remote
panel"). Moved forward from the v2 now-playing panel in the backlog: the user
asked for a skip button while watching a queue, and the only way so far was
the OSD and the arrows.

## Scope

- Actions `next` and `previous`: `Player.GoTo` with `"to": "next"` /
  `"previous"` on the active player, like `playpause` and `stop` (`nothing
  playing` when there is no player). They change the state the shell shows,
  so the daemon reads the state again after them.
- Remote keys `.` (next) and `,` (previous), Kodi's own keyboard keys for
  them, and buttons with tooltips. Fullscreen moves from the row under the
  pad into the pad to make room: previous, play/pause, next; stop, on-screen
  menu, fullscreen.
- `Protocol.js` accepts the two actions for IPC `control`.
- SPEC, README and CHANGELOG list them.

## Not in this ticket

- `play` keeping the queue (backlog). The rest of the v2 now-playing panel
  (the queue list, jumping to an entry, seek bar).

## Done when

- [x] Unit tests against the fake: `next` and `previous` call `Player.GoTo`
      with the active player's id; nothing playing gives `nothing playing`.
      The JS action list matches the Python one; `.` and `,` map to the
      actions.
- [ ] Live, by the user while watching: with 3 queued videos, `.` and the
      next button go to the next one, `,` and the previous button go back;
      `.` on the last item (what happens is noted in the live checks).
