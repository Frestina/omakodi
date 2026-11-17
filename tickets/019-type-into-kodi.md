---
id: 019
title: Type into Kodi's keyboard from the remote
milestone: M2
depends_on: [007, 008, 010, 018]
---

## Goal

When Kodi shows its on-screen keyboard (searching for a TV show, say), the
remote shows a text field and what you type appears on the TV (SPEC "Remote
panel", "Daemon protocol"). Moved from the v2 backlog after the ticket 012
live check: picking letters with the arrows is too slow.

## Scope

- Daemon: on `Input.OnInputRequested` from the event port, state gains
  `"input": {"type", "title", "value"}`; on `Input.OnInputFinished`, or when
  the event port reconnects, `"input": null`. For `password` and
  `numericpassword`, `value` is always `""`.
- Daemon command `{"cmd": "text", "text": "…", "done": false}` →
  `Input.SendText`. Text bounded like other strings (300 chars).
- Service: `input` in its state and in IPC `status()`; `sendText(text, done)`.
- Remote: while `input` is set, a text field above the buttons, with Kodi's
  title and value, takes the keyboard. Typing sends the text (`done: false`,
  coalesced so a fast typist doesn't queue a call per letter); Enter sends
  it with `done: true`; Esc sends `Input.Back` (Kodi's keyboard closes).
  When `input` goes back to null the field goes and the remote keys work
  again. Password types show dots.
- If the remote is closed when Kodi asks, nothing happens; opening it shows
  the field.

## Not in this ticket

- `omakodi text` in the terminal. Number, date and time input beyond what
  `Input.SendText` already handles.

## Done when

- [x] Unit tests against the fake: the requested/finished notifications set
      and clear `input`; a password request never carries its value;
      `text` calls `Input.SendText` with `text` and `done`.
- [ ] Live, with the user's go-ahead: search for a TV show in Kodi by typing
      on the laptop, Enter runs the search; Esc closes Kodi's keyboard.
