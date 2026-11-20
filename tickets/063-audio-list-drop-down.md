---
id: 063
title: The audio track list as a drop-down under its key, like the phone remote
milestone: M9
depends_on: [051, 055, 058]
---

## Goal

The audio track list opens as a drop-down under the audio key, as on
the phone remote, instead of under the now-playing bar (backlog, from
045).

## Scope

- SPEC first ("Audio tracks", the remote panel).
- Read how the phone remote shows its list (read-only): where it sits,
  its width, rows, how it closes.
- The list hangs from the audio key in the action row, over the keys
  below it; rows and their words as 051/055 (the playing track in the
  accent colour and bold); Up/Down, Enter, Esc, `a` and a click outside
  as now. 058's messages unchanged.
- On the now-playing page (045), where the audio key isn't shown: keep
  what it does today unless the phone does otherwise.

## Done when

- [x] Unit tests: where the list opens, keys and closing.
- [ ] Live, by the user: the list drops down from the key like the
      phone's.
