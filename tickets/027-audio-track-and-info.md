---
id: 027
title: Audio track picker and player info
milestone: M5
depends_on: [023]
---

## Goal

Choose the audio track (language, commentary) of what plays, and open
Kodi's player process info (codec, resolution, dropped frames) from the
remote.

## Scope

- SPEC first.
- Daemon: the state gains the audio streams and the current one
  (`Player.GetProperties` `audiostreams`, `currentaudiostream`: name,
  language, codec, channels; bounded); command `audio` with an index →
  `Player.SetAudioStream`.
- Remote: a key cycles through the tracks (and shows which), or a small
  list; a key opens Kodi's `playerprocessinfo` overlay on the TV.

## Done when

- [x] Unit tests: streams in the state, `SetAudioStream` with the index,
      bad indexes refused.
- [x] Live, by the user: switch the audio track of a video that has two;
      player info opens on the TV. *2026-11-18: the user: "it works"; they
      would rather pick the track from a list than step to the next →
      ticket 033.*
