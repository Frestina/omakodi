---
id: 053
title: The phone remote's other messages
milestone: M7
depends_on: [048]
---

## Goal

The messages 048 didn't cover use the phone remote's words too, naming
the box. The user (2026-11-20): "same as" the phone.

## Scope

- SPEC first ("Messages").
- Waking: "No MAC address saved for <box>. Connect once while it's on,
  or add it in the box's settings.", "Invalid MAC address for <box>".
- Soundbar: "Couldn't reach <box>: <why>" when the packet can't be sent.
- Sending a link: "No link found" for text without one, "Nothing to
  send" for an empty clipboard, "Neither the YouTube add-on nor
  SendToKodi is installed on <box>", and the play/queue messages ending
  " with SendToKodi" or " with the YouTube add-on" when that's how it
  played.
- In the remote: "No audio streams to choose from".
- Kodi's errors: "Wrong username or password for <box>", "<box> answered
  HTTP <code>", "Bad address for <box>", "Unexpected reply from <box>";
  the top bar and the terminal keep the fix under them.
- Read the phone remote's code (read-only) for the exact meaning of
  each; write them in omakodi's own words where that changes nothing.

## Done when

- [x] Unit tests: every message's wording and when it shows.
- [x] Live, by the user: waking without a MAC address, an empty
      clipboard and a wrong password read like the phone. *2026-11-20: the user's check passes.*
