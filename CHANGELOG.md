# Changelog

All notable changes to omakodi. Versions follow [Semantic Versioning](https://semver.org/).

## 0.1.0 (2026-11-18)

The first release.

### Added

- **Play and queue a link** from the clipboard with a key: YouTube links go
  to the YouTube add-on with SendToKodi as the fallback (`youtubeMode` picks
  how), everything else to SendToKodi. Queue plays at once when nothing is
  playing; play while the queue plays keeps it and plays the link next. A notification gives the result.
- **The remote:** a panel below the bar on the focused monitor, driven from
  the keyboard (arrows, Enter, Back, Home, play/pause, stop, next/previous in
  the queue, volume, info,
  context and on-screen menus, fullscreen, play/queue the clipboard), with
  buttons for the mouse. It keeps the keyboard while open; a click outside
  closes it. Holding an arrow during a full-screen video skips once.
- **Typing into Kodi:** when Kodi's on-screen keyboard is open, the remote
  shows a text field; the text appears on the TV as you type, Enter sends it.
  Password prompts show dots and their text is never reported.
- **The bar widget:** a Kodi icon while Kodi answers, a paused mark, the
  title and time on hover, the urgent colour for a wrong password. Hidden
  while Kodi is away. Optional title beside the icon (`maxTitleLength`).
- **The `omakodi` command:** `status`, `play`, `queue`, `control`, `config`,
  `init`, all usable without the shell.
- **IPC** target `io.github.frestina.omakodi`: `toggleRemote`, `openRemote`,
  `closeRemote`, `play`, `queue`, `control`, `status`.
- `install.sh` to link `omakodi` into `~/.local/bin`, and the keybindings to
  copy into `~/.config/hypr/bindings.lua`.
