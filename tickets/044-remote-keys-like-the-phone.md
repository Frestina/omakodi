---
id: 044
title: The remote's keys like the phone remote
milestone: M7
depends_on: [031, 035, 019]
---

## Goal

The keys under the top strip match the user's phone remote.

## Scope

- SPEC first.
- Action row in the phone's order: audio stream, fullscreen, info,
  **keyboard ("Type text")**, player info. Home moves to the strip (041);
  the context menu stays on a long press of OK (and right click, `c`).
- Long press of OK with the mouse opens the context menu, as on the phone.
- Holding a key with the mouse repeats it like a real remote: after
  0.4 s, then every 0.11 s (arrows, volume), with the same "only once Kodi
  answered" rule as held keyboard keys (017).
- Kodi's own volume steps by Kodi's "volume steps" setting
  (`audiooutput.volumesteps`, read once per box), not a fixed 5%.
- Kept (omakodi's extra): the Soundbar row (`9` `0`).

## Done when

- [ ] Unit tests: the step from Kodi's setting; the repeat timing; the key
      map.
- [ ] Live, by the user: the rows and the held keys feel like the phone.
