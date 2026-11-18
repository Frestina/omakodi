---
id: 034
title: Audio tracks say their language
milestone: M5
depends_on: [033]
---

## Goal

Every audio track in the remote says which language it is, by name
("English", not "eng"), also when the track has a name of its own
(the user's wish after checking 033).

## Scope

- SPEC first.
- Daemon: the track's `language` is the English name of Kodi's code
  (ISO 639-1 `en`, 639-2 `eng` and the older `ger`/`fre` forms, with a
  region: `en-US`, `pt_BR`); an unknown code stays as it is; `und` and
  the like give `""`. A table in the daemon, standard library only.
- Remote: a track reads language · name · codec and channels, with no
  part twice; "Track N" only when there is nothing else.

## Done when

- [x] Unit tests: codes to names, regions, unknown and empty codes, the
      bounds.
- [ ] Live, by the user: the track list shows each track's language.
