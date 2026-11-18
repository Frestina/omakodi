---
id: 028
title: Power menu
milestone: M5
depends_on: [010]
---

## Goal

Kodi's power actions from the remote: Kodi's shutdown menu on the TV,
reboot and shut down the box.

## Scope

- SPEC first.
- Actions: `shutdownmenu` (`GUI.ActivateWindow` `shutdownmenu`), `reboot`
  (`System.Reboot`), `shutdown` (`System.Shutdown`); only what
  `System.GetProperties` (`canreboot`, `canshutdown`) allows.
- Remote: a power button opens a small menu; reboot and shut down ask
  again before they run (a second press or a confirm row), so a stray key
  never turns the box off.
- After shut down, the remote says Kodi is off instead of "isn't answering".

## Done when

- [ ] Unit tests: the actions, the capability check, the confirmation.
- [ ] Live, by the user: the shutdown menu opens on the TV; reboot comes back.
