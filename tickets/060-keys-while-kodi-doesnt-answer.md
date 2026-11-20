---
id: 060
title: Keys while Kodi doesn't answer, like the phone remote
milestone: M7
depends_on: [043, 053, 058]
---

## Goal

While the box is Offline, the remote's keys look and work as always,
as on the phone remote: they are never dimmed, and a press says Kodi's
error ("Can't reach <box>", or 053's wording for the error there is)
instead of doing nothing. The user (2026-11-20): same as the phone.

## Scope

- SPEC first (the remote's keys, "Messages", the top bar's Offline).
- No row of keys is dimmed while Offline: the D-pad, the action row, the
  strip of five, the Soundbar row and the volume keys.
- A key that needs Kodi, pressed while Offline: the short message with
  Kodi's error for the box (as an error, until the next key), nothing
  sent. Keys that don't need Kodi keep working (the power menu's Wake up
  and Turn on soundbar, Settings, Kodi boxes, ☰).
- Read the phone remote (read-only) for which keys still work and what
  each says while its box can't be reached.
- The top bar keeps showing Offline with the fix under it (043, 053).

## Done when

- [x] Unit tests: each kind of key while Offline (message, nothing
      sent), keys that don't need Kodi still working, back to normal
      when the box answers.
- [x] Live, by the user: with Kodi off, the keys look as usual and a
      press says "Can't reach <box>"; Wake up still works. *2026-11-20: the user's check passes.*
