---
id: 010
title: Remote panel
milestone: M2
depends_on: [008]
---

## Goal

A remote driven from the keyboard (SPEC "Remote panel").

## Scope

- Panel on the focused monitor, keyboard focus while open, Esc closes.
- Key map from SPEC; buttons for mouse use; now-playing line; last result.
- Not reachable: message and fix, keys disabled.
- RTL: Left/Right via `Util.readingKey(event)`. Strings in `i18n/en.json`.
  Use the omarchy-panel-overlay skill.

## Done when

- [ ] Every key in the SPEC table sends the right action (checked against the fake's call log).
- [ ] Opens on the monitor with focus; a second toggle closes it.
- [ ] Markup-shaped titles show literally.
- [ ] Holding an arrow key repeats without piling up a backlog (key repeat is coalesced or bounded).
