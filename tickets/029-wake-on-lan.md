---
id: 029
title: Wake-on-LAN
milestone: M5
depends_on: [028]
---

## Goal

Turn the Kodi box on from the remote when it is off.

## Scope

- SPEC first.
- On a successful connection the daemon reads the box's MAC
  (`XBMC.GetInfoLabels` `Network.MacAddress`) and keeps it in
  `~/.local/state/omakodi/` (or `mac` in the config overrides it).
- While Kodi isn't answering and a MAC is known, the remote offers "Wake
  Kodi": a magic packet to the broadcast address (UDP 9), standard library
  only. `omakodi wake` in the terminal.
- README: the box must have Wake-on-LAN on (LibreELEC: a setting; a wired
  connection), and what the MAC file holds.

## Done when

- [ ] Unit tests: the MAC is saved and validated, the packet's bytes.
- [ ] Live, by the user: shut the box down (028), wake it from the remote.
