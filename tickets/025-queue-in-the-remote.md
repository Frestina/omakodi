---
id: 025
title: The queue in the remote
milestone: M5
depends_on: [021, 023]
---

## Goal

See what is queued, jump to any entry and take one out, from the remote.

## Scope

- SPEC first.
- Daemon: the state gains `queue`: up to 100 entries of the video playlist
  (`Playlist.GetItems`, label/title only, never the file) and the playing
  position; read again on `Playlist.OnAdd`/`OnRemove`/`OnClear` and on a new
  item.
- Remote: a Queue section below the buttons, opened and closed with a key,
  the playing entry marked. Arrows move in the list while it has focus,
  Enter plays that entry (`Player.Open` of the playlist position), a key
  removes it (`Playlist.Remove`; not the playing one). The remote must still
  fit on a 800 px tall screen: the list scrolls.
- Daemon commands `goto` and `remove` with a position, bounded and checked.

## Done when

- [ ] Unit tests: queue state from the fake, goto and remove calls, the
      playing entry can't be removed, the list is bounded.
- [ ] Live, by the user: jump to an entry, remove one, queue a link and see
      it appear.
