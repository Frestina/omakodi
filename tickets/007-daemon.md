---
id: 007
title: Daemon protocol
milestone: M2
depends_on: [003, 005]
---

## Goal

`omakodi daemon` gives the shell a live view of Kodi and runs its commands,
as in SPEC "Daemon protocol".

## Scope

- Line-based JSON on stdin/stdout; exits when stdin closes.
- Command worker so a slow `play` (up to 30 s verdict) doesn't block arrow
  keys; remote actions run in order.
- State pushes on change; 5 s poll while playing; 5 s retries while failing;
  `reachable` false only after 45 s of continuous failure.
- Bad input lines are answered with an error, never crash the daemon.

## Done when

- [ ] Tests drive the daemon over pipes against the fake: state on connect, on `Player.OnPlay`, after the fake goes away (45 s, with a fake clock).
- [ ] An arrow key sent during a pending `play` is answered before the play's result.
- [ ] Closing stdin ends the process within 1 s.
- [ ] Output never contains the password or an item's `file`.
