# Changelog

All notable changes to omakodi. Versions follow [Semantic Versioning](https://semver.org/).

## Unreleased

### Added

- **SendToKodi failures are reported**: `play` (and the play keybinding's
  notification) waits until SendToKodi's link plays, up to a minute, and
  says "SendToKodi couldn't play it" when it gives up, instead of
  "Playing on Kodi…" at once.
- **Settings** in the remote (in the ☰ menu, or `S`), as on a phone
  remote: under *Sharing*, *YouTube links* chooses the mode (Smart,
  YouTube add-on first, SendToKodi only, YouTube add-on only), saved for
  the box and used by every play and queue, the keybindings' included. In
  Smart mode it shows until when SendToKodi is used after a failure, with
  *Try the YouTube add-on again*. The config file's `youtubeMode` is now
  only the starting mode.
- **Shortcut buttons**: a strip of five under the remote's top bar (Home,
  Movies, TV shows, Music, Send a link), as on a phone remote. Each can be
  changed to one of Kodi's screens, library sections, add-ons and their
  folders, favourites or sources (chosen from what Kodi lists), a typed
  path, or Send a link, with Kodi's artwork or a built-in icon; kept per
  box. `1`–`5` open them, `e` then a number changes one, and
  `omakodi shortcut N` opens one from a terminal.
- **Send a link** dialog: type or paste a link, then Play or Queue. It
  replaces the Play link and Queue link buttons; `p` and `q` still send
  the clipboard.
- **Several Kodi boxes**: *Manage Kodi boxes* in the ☰ menu (or `b`)
  opens *Kodi boxes*, as on a phone remote: the saved boxes (click to switch,
  pencil to edit), boxes found on the network (zeroconf, through
  `avahi-browse`) and *Add manually*. The editor tests the connection
  ("✓ Kodi 21.3") and saves to the config file, which becomes a list of
  boxes; the old one-box file keeps working. The bar, the keybindings and
  `omakodi` follow the box in use; `omakodi boxes` and `omakodi box NAME`
  list and switch from a terminal. The MAC address, the volume keys'
  finding, the YouTube mode and the YouTube add-on's failure are now kept
  per box (the old files are read as they are).
- **A top bar like a phone remote's**: ☰, the box's name with
  *Connected*, *Offline* or *Connecting…* under it (why and the fix stay
  under Offline), power and close. The ☰ menu (`M`, or a click on the
  name) lists the boxes to switch between, *Manage Kodi boxes*,
  *Settings* and the version; the cog and box buttons are gone.

### Changed

- **The power menu** follows a phone remote's: *Wake up (Wake-on-LAN)*,
  *Turn on soundbar (HDMI-CEC)*, *Kodi power menu*, then *Reboot* and
  *Shut down* (still only when Kodi allows them). It works while Kodi
  isn't answering, replacing the "Wake Kodi" button (`"wakeOnLan": false`
  hides Wake up). Reboot and Shut down ask in a dialog ("Reboot Living
  room?", Cancel or Reboot) instead of a second press. The volume and
  "Nothing playing" left the header.
- **The remote's keys** follow a phone remote's: the action row is audio
  track, fullscreen, info, *Type text* (`k`: Kodi's keyboard, or "Kodi
  isn't asking for text right now") and player info. Home is on the
  shortcut strip; the context menu is a long press of OK (or a right
  click, or `c`). Held with the mouse, the arrows and volume keys repeat
  like a real remote's (after 0.4 s, every 0.11 s). Kodi's own volume
  steps by Kodi's *Volume control steps* setting (1% by default) instead
  of 5%.
- **Now playing** follows a phone remote's: the bar at the bottom shows
  the thumbnail, title and subtitle with stop, play/pause and next. A
  click on it (or `n`) opens the now-playing page: the artwork large, a
  seek bar with the time played, "Paused" or "Speed: 2x", and the length
  and when it ends ("47:20 · ends 21:40"), then previous, rewind,
  play/pause, fast-forward and next; it closes when playback stops. Its
  **Queue** (`u`) and **Details** (`d`) open as dialogs over it; the
  queue says "Loading…" or "The queue is empty", a click plays an entry,
  and Delete or × still takes one out.
- **Details** follow a phone remote's: the title and subtitle, the
  Overview with the whole plot (scrolling; `D` is gone), badges with the
  video and audio codecs (4K, HEVC, Dolby Vision, DD+, 5.1 …), an Info
  row per field with its icon (channel, genre, show, the date aired or
  premiered, studio, rating with votes, age rating, runtime, director,
  writer, country), and the cast as cards with photos, fetched through
  the art cache. Fields add-ons fill only in Kodi's player labels show
  too.
- **Links in the details**, as on a phone remote: the plot's web links (a
  YouTube description's) are underlined in the accent colour; a click
  opens one in the default browser and closes the remote, Tab / Shift+Tab
  mark the next or previous link and Enter opens it. Only http and https
  links open; the rest of the plot stays plain text.
- **Kodi's keyboard** follows a phone remote's: when Kodi asks for text,
  a dialog opens over the remote with Kodi's prompt ("Send text to Kodi"
  without one), a text field (dots for a password), Paste, Cancel and
  Send. Send (or Enter) gives Kodi the whole text at once and submits it;
  nothing is sent while typing. Cancel (or Esc) leaves Kodi's keyboard on
  the TV, and *Type text* (`k`) opens the dialog again.
- **Messages** follow a phone remote's and name the box: "Playing on
  Living room…", "Queued on Living room (3 in queue)", "Can't reach
  Living room", "Nothing is playing", "Wake-up sent to Living room",
  "Soundbar wake-up sent to Living room", "YouTube is still loading on
  Living room", "SendToKodi isn't installed on Living room". In the remote
  they show as a short message over the bottom that goes after 3 s (an
  error stays until the next key) instead of a line that stays; the play
  and queue keybindings show one notification that updates, in the same
  words.
- **Audio tracks** read as on a phone remote: the language, then Kodi's
  name for the track ("English · Director's commentary"); the codec and
  channels as Kodi says them ("Norwegian · EAC3 5.1") only for a track
  without a name, else "Audio 2". The playing track is in the accent
  colour and bold, without the ▶ and the numbers.
- **Bold, italics and colours in the details**, as on a phone remote: the
  overview shows Kodi's `[B]`, `[I]` and `[COLOR …]` (a YouTube
  description's channel and views, say) instead of plain text; `[CR]`
  still breaks the line and Kodi's other tags still go. Titles and the
  other one-line fields stay plain.
- **The other messages** follow it too: "No MAC address saved for Living
  room. Connect once while it's on, or add it in the box's settings.",
  "Couldn't reach Living room: Network is unreachable" (the soundbar),
  "No link found", "Nothing to send" (an empty clipboard), "No audio
  streams to choose from", and Kodi's errors: "Wrong username or password
  for Living room", "Living room answered HTTP 500", "Unexpected reply
  from Living room", "Bad address for Living room". The top bar and the
  terminal show the fix on the line under them.
- **Kodi boxes are known by an id**, as on a phone remote, not by their
  address: two boxes on one address can both be saved, a box keeps its
  shortcut buttons, YouTube mode, MAC address and soundbar finding when
  its address changes, and Delete takes them away with the box. The
  config and state files move over by themselves the first time the
  remote runs (each box gets an `id`; nothing else in the config
  changes).

### Fixed

- **A box address that can't be one** (`kodi..lan`, one with a port in
  it) says "Bad address for <box>" instead of an internal error; nothing
  is sent to it.

- **Stopping a video while it starts** (`x`, `omakodi control stop`) no
  longer reads as a failure: the YouTube video isn't opened again with
  SendToKodi, and `smart` mode doesn't avoid the YouTube add-on for 30
  minutes.

## 0.2.0 (2026-11-18)

The complete remote: what plays, the queue, details, audio tracks, power,
the soundbar and Kodi's own volume.

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

### Changed

- **`+` `-` `m` act on Kodi's own volume.** In 0.1.0 they sent Kodi's
  volume keys, which Kodi passes to the TV or soundbar over HDMI-CEC when
  it is set up to; that is now the Soundbar row (`9` `0`). `omakodi
  control volup`/`voldown`/`mute` changed the same way; the old behaviour
  is `soundbarup`/`soundbardown`.

### Fixed

- While Kodi isn't answering, a long error no longer pushes the fix ("Is
  Kodi on…") out of the remote's header.

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
