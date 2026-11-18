# Changelog

All notable changes to omakodi. Versions follow [Semantic Versioning](https://semver.org/).

## Unreleased

### Added

- **Seek bar** in the remote: click or drag to jump, elapsed / total and the
  time it ends, with rewind and fast-forward beside it (`<` and `>`).
  `omakodi seek`, IPC `seek(seconds)`.
- **Artwork** in the remote: the poster or thumbnail of what plays, fetched
  by the daemon with the login and cached in `~/.cache/omakodi/art/`.
- **The queue** in the remote (`u`): see what is queued, play any entry,
  take one out. A queued YouTube link shows its title (asked from YouTube's
  oEmbed, see SECURITY.md) instead of Kodi's "play" until it plays.
- **Details card** in the remote (`d`): plot, genres, year, studio, rating,
  cast, and badges for resolution, HDR and audio; `D` shows the whole plot.
- **Power menu** (`P` or the power button): Kodi's power menu on the TV,
  reboot and shut down (asked twice; only what Kodi allows). The remote
  then says Kodi is off or restarting instead of "isn't answering".
- **A new layout for the remote**: links, volume, actions and a big D-pad,
  with what plays at the bottom (`n` or a click shows the seek bar,
  details and queue) and its poster blurred behind the remote.
- **Audio tracks**: `a` or a button opens the list of audio tracks of what
  plays, each with its language ("English · Commentary · AC3 5.1"); pick
  the one you want (`omakodi audio INDEX`). `I` or a button opens Kodi's player info on
  the TV (`omakodi control playerinfo`).
- **Kodi's own volume and the soundbar's**: `+` `-` `m` now change Kodi's
  own volume (the "Volume" the remote shows); a **Soundbar** row (`9` `0`)
  sends Kodi's volume keys over HDMI-CEC to the TV or soundbar, and
  hides itself on a box without CEC volume. `omakodi volume N`.
- **Turn on the soundbar** (power menu, `s`, `omakodi control soundbaron`):
  Kodi becomes the active HDMI source over CEC, which wakes the soundbar
  (Kodi's *Force AVR to wake up when Kodi is activated*), through Kodi's
  EventServer (UDP 9777).
- **Wake-on-LAN**: while Kodi is off or isn't answering, "Wake Kodi" (or
  `w`; `omakodi wake`) turns the box on, with the MAC address omakodi read
  while Kodi was on (or `mac` in the config). `wakeOnLan: false` turns it
  off for a box that can't be woken.

## 0.1.0 (2026-11-18)

The first release.

### Added

- **Play and queue a link** from the clipboard with a key: YouTube links go
  to the YouTube add-on with SendToKodi as the fallback (`youtubeMode` picks
  how), everything else to SendToKodi. Queue plays at once when nothing is
  playing; play while the queue plays keeps it and plays the link next. A
  notification gives the result.
- **The remote:** a panel below the bar on the focused monitor, driven from
  the keyboard (arrows, Enter, Back, Home, play/pause, stop, next/previous in
  the queue, volume, info, context and on-screen menus, fullscreen, play/queue the clipboard), with
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
