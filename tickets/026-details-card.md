---
id: 026
title: Details card
milestone: M5
depends_on: [023, 024]
---

## Goal

A card in the remote with what Kodi knows about the playing item: plot,
genres, year, studio, rating, cast, and stream badges (resolution, HDR,
audio channels and codec).

## Scope

- SPEC first. Opened and closed with a key (Kodi's own info stays on `i`).
- Daemon: `Player.GetItem` properties on a new item only (not every poll),
  all bounded text; the plot cut to a few lines with the rest on demand.
- Empty fields are left out; add-on items (often no metadata) show what
  there is.

## Done when

- [ ] Unit tests: the details are read once per item, bounded, plain text.
- [ ] Live, by the user: a library movie or episode shows its details; a
      YouTube video shows what it has.
