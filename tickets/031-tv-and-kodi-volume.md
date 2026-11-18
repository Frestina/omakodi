---
id: 031
title: TV volume and Kodi volume
milestone: M5
depends_on: [023]
---

## Goal

Keep `+`/`-`/`m` driving the soundbar over HDMI-CEC, as now, and add Kodi's
own volume as a second control. The remote's "Volume 100%" stops
pretending to be the soundbar's.

## Scope

- Live first, with the user's go-ahead: confirm that `Application.SetVolume`
  with a number changes Kodi's own volume without CEC (step up/down and mute
  go over CEC to the soundbar).
- SPEC first, then: Kodi volume keys or a slider (absolute
  `Application.SetVolume`); the remote shows "Kodi volume N%" only for that
  control, and nothing for the soundbar (Kodi can't read its level).
- Detect CEC volume: a `volup` that didn't change Kodi's volume means it
  went to the TV/soundbar; remember that and label the keys "TV volume".
- Note: with audio passthrough, Kodi's own volume has no effect.

## Changed with the user (2026-11-18)

The first build kept `+` `-` `m` on the soundbar and added a Kodi volume
slider. The user asked for the reverse: `+` `-` `m` on Kodi's own volume
(a number, mute true/false; checked live), and the soundbar as the second
control: a row of step keys (`9` `0`, `soundbarup` `soundbardown`; the
user dropped a soundbar mute, `m` is enough), since Kodi can't read the soundbar's level for a slider.
The CEC detection now runs on the soundbar keys and hides the row when
they only move Kodi's own volume.

## Done when

- [x] Live check of the two paths recorded. *2026-11-18, in the
      git-ignored live-checks file: a number set Kodi's own level (the user
      heard it); increment/decrement left it at 90 (over CEC).*
- [x] Unit tests: absolute volume, the CEC detection.
- [ ] Live, by the user: `+` `-` `m` change Kodi's own volume; the
      soundbar row steps the soundbar.
