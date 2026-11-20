---
id: 064
title: Small fixes from the backlog
milestone: M9
depends_on: [047, 048, 062]
---

## Goal

The small open items in the backlog, fixed in one go (the user,
2026-11-20: "fix backlog").

## Scope

- SPEC first where it describes these.
- **The bar widget's tooltip** says Kodi's error the way the remote and
  the notifications do since 048/053 ("Can't reach <box>", "Wrong
  username or password for <box>", …), not Kodi's error in full.
- **Without the event port**, the keyboard key (`k`) that found Kodi's
  keyboard asks Kodi again whether it is still open before opening the
  dialog, and stops being marked once Kodi says no (047's daemon command).
- **`install.sh` and the README** list the same files as left behind
  after removal (the README's list is the right one unless install.sh
  knows better; check what removal really leaves).

## Done when

- [ ] Unit tests: the tooltip's wording for each error, the keyboard key
      without the event port, the removal list (a test that the two
      lists match, if it's cheap).
- [ ] Live, by the user: the bar's tooltip with Kodi off.
