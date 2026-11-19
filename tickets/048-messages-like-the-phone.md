---
id: 048
title: Messages like the phone remote
milestone: M7
depends_on: [043]
---

## Goal

What omakodi says matches the user's phone remote, naming the box.

## Scope

- SPEC first.
- The phone's wording, with the box's name (043): "Can't reach <box>",
  "Nothing is playing", "Wake-up sent to <box>", "Soundbar wake-up sent to
  <box>", "Playing on <box>…", "Queued on <box> (3 in queue)", "YouTube is
  still loading on <box>", "YouTube add-on couldn't play it, trying
  SendToKodi…", "SendToKodi isn't installed on <box>". Kept (omakodi's
  extras): the messages for SendToKodi failures (038) and a stop (039).
- In the remote, a short message that shows for a few seconds and goes,
  like the phone's, instead of a status line that stays; errors stay
  until the next action. The keybindings' notifications use the same
  words.

## Done when

- [x] Unit tests: every message's wording.
- [ ] Live, by the user: play, queue, wake, soundbar and an unreachable
      box read like the phone.
