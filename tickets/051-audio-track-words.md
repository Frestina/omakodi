---
id: 051
title: Audio track words like the phone remote
milestone: M7
depends_on: [034, 046]
---

## Goal

The audio track list words its tracks as the phone remote does. The
user (2026-11-20): "same as" the phone remote.

## Scope

- SPEC first ("Audio tracks", "Details").
- The badges stay as they are (DD, DD+, TrueHD, DTS, DTS-HD MA, …; 046
  already follows the phone).
- Each track in the list: the language's name, then Kodi's own name for
  the stream (its tags removed), joined with " · ". Only when Kodi gives
  the stream no name: the codec as Kodi says it, upper case (AC3, EAC3,
  TRUEHD, DTS), and mono / stereo / 5.1 / 7.1 / "N ch". With nothing
  known: "Audio N". The current track in the accent colour and bold.
- Check the phone remote's code (read-only) for anything this misses.

## Done when

- [ ] Unit tests: a named stream, an unnamed one, one with nothing known,
      tags removed, the current track marked.
- [ ] Live, by the user: the list reads like the phone's for a film and
      a YouTube video.
