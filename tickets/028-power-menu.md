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

- [x] Unit tests: the actions, the capability check, the confirmation.
- [x] Live, by the user: the shutdown menu opens on the TV; reboot comes back.
      *2026-11-18: the user: "it worked". Shut down ("Kodi is off") was to
      be checked with 029's wake-up; the user dropped that check (their
      box is a Raspberry Pi, which can't be woken), so it isn't checked
      live.*
