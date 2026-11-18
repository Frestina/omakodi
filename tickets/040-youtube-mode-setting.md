---
id: 040
title: youtubeMode as a bar widget setting
milestone: M6
depends_on: [005, 009]
---

## Goal

Choose `youtubeMode` in the bar widget's settings (`omarchy bar set`; Omarchy 4
has no settings window for widgets, found 2026-11-18,
`shell.json`) instead of editing `~/.config/omakodi/config.json`.

## Scope

- SPEC first. The open question to settle there: the keybindings run
  `omakodi play --clipboard` as their own process, which doesn't read
  `shell.json`. Options: the service passes the mode to the daemon and the
  keybindings go through the shell's IPC (`play(text)` already exists, with
  the clipboard read by the service), or the CLI reads the widget's entry
  in `shell.json`. Pick one; the config file's `youtubeMode` stays as the
  fallback for the terminal and for anyone who set it.
- `manifest.json`: a `youtubeMode` choice in the bar widget schema, with
  the four modes and their descriptions; default `smart`.
- README: where to set it and which wins when both are set.

## Done when

- [x] Unit tests: the widget's mode reaches play/queue; the config file's
      still works without it; a bad value falls back to `smart`.
      *Chose option 2 with the user: `omakodi` reads the widget's entry in
      `shell.json` itself, so the keybindings stay. A bad value falls back
      to the config file's mode (default `smart`).*
- [x] `omarchy plugin validate` passes with the new schema.
- [ ] Live, by the user: change the mode with `omarchy bar set`; the next
      play follows it, from the remote and from the keybinding.
