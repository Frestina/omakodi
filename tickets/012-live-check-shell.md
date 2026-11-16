---
id: 012
title: Live check on this machine
milestone: M2
depends_on: [009, 010, 011]
---

## Goal

omakodi runs in the real shell against the real Kodi, and the user uses it for
a few days before release.

## Scope

- Link the checkout into `~/.config/omarchy/plugins/io.github.frestina.omakodi`,
  enable, add the bindings.
- Check widget states, the remote, play/queue from the keys, and leaving
  home (Kodi unreachable) and coming back.
- Collect what the user finds; each becomes a ticket or backlog item.

## Done when

- [ ] Every SPEC "Shell surfaces" behaviour seen live, recorded in `docs/live-checks.local.md`.
- [ ] The user has used it for some days and their findings are filed.
