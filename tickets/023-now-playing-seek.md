---
id: 023
title: Now playing in the remote: seek bar, end time, rewind and fast-forward
milestone: M5
depends_on: [010, 020]
---

## Goal

The top of the remote shows where the video is: a seek bar, elapsed/total
and the time it ends, and lets you jump in it. First of the v2 remote (the
user chose to grow the remote, not add a second panel).

## Scope

- SPEC "Remote panel" and "Daemon protocol" first: the now-playing area,
  new actions and keys.
- A seek bar under the title: drag or click to seek (`Player.Seek` to a
  time), elapsed / total, "ends HH:MM" (local clock, 24 h). The position
  moves smoothly between the daemon's 5 s polls (QML counts while playing).
- Rewind and fast-forward actions (Kodi's `rewind` / `fastforward`, which
  step the speed) with keys and buttons. Keys are letters or keys that need
  no AltGr on a Norwegian layout; checked against the existing map.
- Live streams (no total) show elapsed only, no seek bar.
- `omakodi control` and IPC gain the new actions.

## Done when

- [ ] Unit tests against the fake: seek sends `Player.Seek` with the time;
      rewind/fast-forward send their actions; the key map has no clashes.
- [ ] Live, by the user: seek by click and drag, rewind and fast-forward on a
      real video; the end time is right.
