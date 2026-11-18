---
id: 047
title: Kodi's keyboard like the phone remote
milestone: M7
depends_on: [019, 044]
---

## Goal

When Kodi asks for text, the remote asks the way the user's phone remote
does.

## Scope

- SPEC first.
- A dialog over the remote titled with Kodi's prompt (or "Send text to
  Kodi"): a text field (dots for a password), a **Paste** button,
  **Send** and **Cancel**. Send (Enter) sends the text once and submits
  it (`Input.SendText` with `done`); Cancel (Esc) only closes the dialog,
  and Kodi's keyboard stays on the TV. No live typing.
- The **keyboard key** (044) opens the dialog again while Kodi asks for
  text, or says "Kodi isn't asking for text right now".

## Done when

- [ ] Unit tests: the dialog's states; what is sent.
- [ ] Live, by the user: a search in Kodi from the dialog, like the phone.
