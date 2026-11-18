---
id: 038
title: Report SendToKodi failures
milestone: M6
depends_on: [004, 005]
---

## Goal

When SendToKodi can't play a link (a removed video, a login wall), say so
on the laptop too. Today `play` answers "Playing on Kodi…" as soon as
SendToKodi has the link, and only the TV shows yt-dlp's error.

## Scope

- Live first, with the user's go-ahead: send a link SendToKodi can't play
  and record what Kodi's event port and log show (`Player.OnStop` before
  `Player.OnAVStart`? an `Other.*` notification? nothing?), and how long a
  working SendToKodi link takes to start.
- SPEC first, then: after opening a SendToKodi item, watch it like the
  YouTube verdict (listening before opening, "new item" as there), with a
  longer limit (SendToKodi can take 20 s or more): playing → "Playing on
  Kodi"; failed → `SendToKodi couldn't play it` (an error, with the
  notification for `--notify`); undecided at the limit → "Sent to Kodi;
  it is still loading".
- `progress` lines while waiting ("SendToKodi is opening it…"), so the
  remote and a `--notify` keybinding don't look stuck.
- Queue: no watch (it plays later), as now.

## Done when

- [ ] Live check of a failing and a working SendToKodi link recorded.
- [ ] Unit tests with the fake Kodi: playing, failed, undecided, the old
      video still playing while the new one loads.
- [ ] Live, by the user: a broken link says it failed; a good one plays
      as before.
