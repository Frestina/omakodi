---
id: 006
title: Live check from the terminal
milestone: M1
depends_on: [003, 005]
---

## Goal

Every `omakodi` command works against a real Kodi before any shell UI exists.

## Scope

- Real config on this machine (mode 600), not in the repo.
- Run each `control` action, `status`, `play` and `queue` with a YouTube link,
  a non-YouTube link (SendToKodi), and a YouTube link that fails (e.g. a
  removed video) to see the fallback.
- Record results, Kodi and add-on versions in `docs/live-checks.local.md`
  (git-ignored). Fix found bugs in new tickets or here if they block.

## Done when

- [ ] Every row of SPEC "Remote commands" checked on the real box.
- [ ] Play and queue checked for both add-ons; fallback seen once.
- [ ] Away-from-home behaviour checked (Kodi unreachable → `not reachable`, exit 4, within ~5 s).
