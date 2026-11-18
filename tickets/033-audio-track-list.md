---
id: 033
title: Pick the audio track from a list
milestone: M5
depends_on: [027]
---

## Goal

Choose the audio track you want from a list, instead of stepping to the
next one (the user's wish after checking 027).

## Scope

- SPEC first.
- Remote: the audio button, or `a`, opens a list of the tracks under it
  (like the queue list), the playing one marked ▶ and selected first.
  Up/Down choose, Enter or a click plays that track and closes the list;
  `a` or Esc close it. Only one of the details card, the queue list and
  the track list is open at a time.
- The daemon's `audio` command is unchanged.

## Done when

- [x] Unit tests: the key opens the list (not a next-track step).
- [ ] Live, by the user: pick a track from the list on a video that has
      two or more.
