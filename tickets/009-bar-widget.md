---
id: 009
title: Bar widget
milestone: M2
depends_on: [008]
---

## Goal

The bar shows Kodi while it answers, and what is playing (SPEC "Bar widget").

## Scope

- Hidden while not reachable; icon when idle; icon + elided title while
  playing, paused mark when paused.
- Click toggles the remote; tooltip with title/time or the error.
- Plain text everywhere; strings in `i18n/en.json`. Use the
  omarchy-bar-widget skill.

## Done when

- [ ] Checked on every monitor with the fake Kodi: hidden, idle, playing, paused.
- [ ] A title like `<img src="https://example.invalid/x">` shows literally.
- [ ] Vertical bar orientation doesn't break the layout.
