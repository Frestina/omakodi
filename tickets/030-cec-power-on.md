---
id: 030
title: Turn on the soundbar over HDMI-CEC
milestone: M5
depends_on: [028]
---

## Goal

Wake the soundbar from the remote, the way the user's phone remote does:
Kodi becomes the active HDMI source, and Kodi's CEC setting *Force AVR to
wake up when Kodi is activated* wakes the soundbar. (First planned as
"turn on the TV and soundbar"; renamed 2026-11-18 to match what the phone
remote's button does: the TV is the TV's business.)

## Scope

- SPEC first.
- JSON-RPC can't run `CECActivateSource`; Kodi's EventServer (UDP 9777,
  "Allow remote control from applications on other systems") can. The
  daemon sends one EventServer action packet (`CECActivateSource`),
  standard library only; `omakodi control soundbaron`, `s` and a row in
  the power menu.
- README: what the EventServer and the CEC setting need, and that the
  EventServer has no login (anyone on the network who can reach UDP 9777
  can already send it actions).

## Done when

- [x] Unit tests: the packet's bytes against the EventServer format.
      *Checked against Kodi Omega's EventPacket.cpp / EventClient.cpp: no
      HELO needed, so no "new connection" toast on the TV.*
- [ ] Live, by the user: soundbar off, Kodi on, the button (or `s`) turns
      the soundbar on.
