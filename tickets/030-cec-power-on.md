---
id: 030
title: Turn on the TV and soundbar over HDMI-CEC
milestone: M5
depends_on: [028]
---

## Goal

With the Kodi box on and the TV in standby, wake the TV and soundbar and
switch them to Kodi from the remote.

## Scope

- SPEC first.
- JSON-RPC can't run `CECActivateSource`; Kodi's EventServer (UDP 9777,
  "Allow remote control from applications on other systems") can. The
  daemon sends one EventServer action packet (`CECActivateSource`),
  standard library only; `omakodi control tvon` and a remote button.
- README: what the EventServer needs, and that it has no login (anyone on
  the network who can reach UDP 9777 can already send it actions).

## Done when

- [ ] Unit tests: the packet's bytes against the EventServer format.
- [ ] Live, by the user: TV in standby, the button turns on TV and soundbar
      on Kodi's input.
