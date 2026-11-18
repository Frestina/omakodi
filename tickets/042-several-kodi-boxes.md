---
id: 042
title: Several Kodi boxes
milestone: M6
depends_on: [007, 008]
---

## Goal

More than one Kodi in the config, a switcher in the remote, and boxes on
the network found by themselves.

## Scope

- SPEC first: the config format (a list of boxes, each with its own login,
  ports, `mac` and `wakeOnLan`; the current single-box file keeps working),
  which box the bar, the keys and `omakodi` use, and how the remote
  switches (keys, a list in the header).
- Per-box state already keys on `host` (`mac.json`, `volume.json`); check
  the rest (`youtube-failed`, `titles.json`).
- Discovery: Kodi announces `_xbmc-jsonrpc-h._tcp` over zeroconf;
  `avahi-browse` (if installed) lists them, and the remote offers found
  boxes that aren't in the config. No password is ever guessed or sent to
  a found box until the user adds it.
- The daemon follows one box at a time; switching closes the event port
  and reads the new box's state.

## Done when

- [ ] Unit tests with two fake Kodis: the old config, a list, switching,
      per-box state, discovery parsing.
- [ ] Live, by the user: their box from a list config; a second (fake or
      real) box switched to and back.
