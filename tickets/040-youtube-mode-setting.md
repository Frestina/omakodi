---
id: 040
title: Choose the YouTube mode in the remote's Settings
milestone: M6
depends_on: [005, 010]
---

## Goal

Choose which add-on plays YouTube links in the remote, the way a phone
remote does it, instead of editing `~/.config/omakodi/config.json`.

## Changed with the user (2026-11-18)

First planned and built as a bar widget setting in `shell.json`, read by
every `omakodi` process (the user's option 2). Omarchy 4 has no settings
window for widgets (only `omarchy bar set`), and the user wants the
experience to be the same as their phone remote in every way: a Settings
page in the remote, the mode kept per box. The `shell.json` route was
taken out again.

## Scope

- SPEC first.
- A Settings page over the remote (a cog button in the header, `S`), with
  a back arrow: *Sharing* → *YouTube links*, "Which add-on plays the
  YouTube links you send to <box>", the four modes as radio rows in the
  phone remote's order (Smart, YouTube add-on first, SendToKodi only,
  YouTube add-on only) with a line each; a pick saves at once. In Smart
  mode, while SendToKodi is used after a failure: until when, and "Try
  the YouTube add-on again". Keyboard: Up/Down, Enter, Esc/Backspace back.
- Kept per box in `~/.local/state/omakodi/youtube-mode.json`; every
  `omakodi` process reads it for each play or queue; the config file's
  `youtubeMode` is the starting mode. `omakodi config` shows the mode and
  where it came from.
- Daemon: `youtube` in the state (`mode`, `from`, `avoidUntil`, `box`);
  commands `youtubeMode` and `youtubeRetry`.

## Done when

- [x] Unit tests: the chosen mode reaches play/queue and the keybindings'
      process; the config file's without a choice; the state and commands;
      smart mode's wait and trying again.
- [ ] Live, by the user: open Settings, pick a mode; the next play follows
      it, from the remote and from the keybinding; the page looks and
      works like the phone remote's.
