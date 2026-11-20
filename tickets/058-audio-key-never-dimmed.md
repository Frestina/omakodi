---
id: 058
title: The audio key is never dimmed, like the phone remote
milestone: M7
depends_on: [055]
---

## Goal

As on the phone remote, the audio key always looks live. Pressed while
nothing plays it says "Nothing is playing"; pressed with nothing to
choose from it says "No audio streams to choose from". The user
(2026-11-20): yes.

## Scope

- SPEC first ("Audio tracks", the remote's keys, "Messages").
- The key is never dimmed, with or without something playing.
- `a` or a click while nothing plays: the short message "Nothing is
  playing" (048's wording, as Space with nothing playing).
- While something plays with no audio streams: "No audio streams to
  choose from" (053), the list doesn't open.
- One track or several: as in 055 and 051. Picking the playing track
  again only closes the list (the user agreed to keep that, 2026-11-20).
- The tooltip with nothing playing: check what the phone remote shows
  (read-only) and do the same.

## Done when

- [x] Unit tests: nothing playing, no streams, one track, several.
- [x] Live, by the user: the key looks the same with and without
      something playing; pressing it with nothing playing says so. *2026-11-20: the user's check passes.*
