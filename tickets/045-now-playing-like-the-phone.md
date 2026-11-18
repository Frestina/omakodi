---
id: 045
title: Now playing like the phone remote
milestone: M7
depends_on: [023, 024, 025, 026, 035]
---

## Goal

The now-playing bar and a now-playing page as on the user's phone remote.

## Scope

- SPEC first.
- The bar (only while something plays): the thin progress line, the
  thumbnail, title and subtitle, then **stop, play/pause, next** in that
  order; no time line. A click (or `n`) opens the page.
- The now-playing page, over the remote like Settings: a top bar with a
  close arrow (Esc), the title and subtitle, and **Details** and
  **Queue** buttons (Queue always there); the artwork large (a film icon
  without art); the seek bar, with the elapsed time under it (in the
  accent colour while dragging), "Paused" or "Speed: 2x" in the middle,
  and "47:20 · ends 21:40" on the right; then **previous, rewind,
  play/pause (large), fast-forward, next**. It closes when playback stops.
- **Queue** as a dialog: "Loading…", "The queue is empty", the entries
  with the playing one in accent bold, a click (Enter) plays one, a
  **Close** button. Kept (omakodi's extra): removing an entry (Delete, ×).
- Keyboard: the page's keys as now (`<` `>` `.` `,` Space, `d`, `u`).

## Done when

- [x] Unit tests for the pure parts (time and speed lines, queue rows).
- [ ] Live, by the user: bar, page and queue match the phone.
