---
id: 042
title: Several Kodi boxes
milestone: M6
depends_on: [007, 008]
---

## Goal

More than one Kodi in the config, a switcher in the remote, and boxes on
the network found by themselves.

## Widened (2026-11-18, the comparison with the phone remote)

- The ☰ menu (043) lists the boxes; a click switches.
- **Manage Kodi boxes**, a page: **Saved** (name, address:port, edit),
  **Found on your network** ("Searching…", "No new boxes found", add one),
  **Add manually**. The editor: Name, address, Web port, Live port (TCP),
  Username, Password, the Kodi setup help, **Test connection** ("✓ Kodi
  21.3" with Kodi's name, or the error), **Delete**, **Save**. It writes
  the config file (mode 600); the password never reaches the shell's
  logs or the daemon's output.

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

- [x] Unit tests with two fake Kodis: the old config, a list, switching,
      per-box state, discovery parsing.
- [x] Live, by the user: their box from a list config; a second (fake or
      real) box switched to and back. *2026-11-19: the user's check passes.*
