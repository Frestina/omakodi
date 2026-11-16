---
id: 003
title: Remote commands and status
milestone: M1
depends_on: [002]
---

## Goal

`omakodi control <action>` and `omakodi status` do everything in SPEC
"Remote commands".

## Scope

- `lib/omakodi/control.py`: the action table, the fullscreen-video check for
  arrows and select, active player lookup (prefer video).
- `lib/omakodi/nowplaying.py`: build the now-playing object from
  `Player.GetActivePlayers`, `Player.GetItem`, `Player.GetProperties`,
  `Application.GetProperties`. Bounded strings; never the item's `file`.
- `omakodi status` prints it as JSON.

## Done when

- [x] Every action sends the expected method and params to the fake (table-driven test).
- [x] Arrows during plain fullscreen video send the step actions; with OSD or a dialog open, normal navigation.
- [x] `playpause`/`stop` with nothing playing → `nothing playing`, exit 1.
- [x] `status` output never includes `file`, even when the fake returns one with `ApiKey=` in it.
