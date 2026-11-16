---
id: 008
title: Service and IPC
milestone: M2
depends_on: [007]
---

## Goal

`Service.qml` owns the daemon and the shared state, and exposes the IPC
target in SPEC "IPC target".

## Scope

- Start `omakodi daemon` with `Process`, parse stdout lines, restart with
  backoff when it exits, stop it when the plugin is disabled.
- State properties for the widget and panel; request ids for results.
- IPC methods: `toggleRemote`, `openRemote`, `closeRemote`, `play`, `queue`,
  `control`, `status`. Use the omarchy-service-ipc skill.
- Locate `bin/omakodi` from the plugin directory, not PATH.

## Done when

- [ ] `omarchy-shell io.github.frestina.omakodi status` returns the daemon's state.
- [ ] Killing the daemon process: the service restarts it and state recovers.
- [ ] Disabling the plugin leaves no daemon running.
- [ ] `omarchy plugin validate` passes.
