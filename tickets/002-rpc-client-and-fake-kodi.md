---
id: 002
title: JSON-RPC client and fake Kodi
milestone: M1
depends_on: [001]
---

## Goal

One small client for Kodi's HTTP JSON-RPC and TCP event port, tested against a
fake Kodi that the tests and the demo share.

## Scope

- `lib/omakodi/rpc.py`: `call(method, params)` with Basic auth, timeouts
  (connect 4 s, read 10 s, longer per call when needed), error mapping from
  SPEC "Errors". Response size limit (1 MiB).
- `lib/omakodi/events.py`: connect to the event port, split concatenated JSON
  by brace depth outside strings, ping after 30 s idle, reconnect with
  backoff. Yields `(method, data)`.
- `tests/fakekodi.py`: threaded HTTP server checking Basic auth, scripted
  method → result table, a record of calls received; TCP server that sends
  scripted notifications. Binds to 127.0.0.1 on a free port.

## Done when

- [ ] Each error row (unreachable, 401, other HTTP, bad JSON, JSON-RPC error) has a test.
- [ ] The splitter handles two objects in one read, one object across reads, and braces inside strings.
- [ ] The event reader reconnects after the fake drops the connection.
- [ ] No request or error output contains the password (tested).
