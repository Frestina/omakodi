---
id: 055
title: The audio list opens for one track too, like the phone remote
milestone: M7
depends_on: [051]
---

## Goal

With a single audio track, the audio key opens the list (one row, in the
accent colour) as the phone remote does, instead of being dimmed with
"This has only one audio track". The user (2026-11-20): "same as phone".

## Scope

- SPEC first ("Audio tracks", the remote's keys).
- One track: the key is live, `a` and a click open the list with that
  row; Enter on it changes nothing and closes the list.
- No tracks at all: as now ("No audio streams to choose from", 053).
- Check the phone remote (read-only) for anything else it does with one
  track (the tooltip, the key's look).

## Done when

- [x] Unit tests: one track opens the list, none says so, several as
      before.
- [ ] Live, by the user: a YouTube video with one track opens the list
      like the phone's.
