# omakodi specification

A keyboard remote for Kodi on Omarchy. Send a link from the clipboard to play
or queue it, drive Kodi's menus from the keyboard, and see what is playing in
the bar, without picking up a phone.

This file is the source of truth. The work to build it is in
[tickets/](tickets/README.md); later features are in
[tickets/BACKLOG.md](tickets/BACKLOG.md).

## Identity

| | |
| --- | --- |
| Plugin ID | `io.github.frestina.omakodi` |
| Command | `omakodi` |
| Config | `~/.config/omakodi/config.json` |
| State | `~/.local/state/omakodi/` |
| Cache | `~/.cache/omakodi/art/` (artwork) |
| IPC target | `io.github.frestina.omakodi` |
| License | MIT |

## Architecture

```text
 keybinding / bar click / terminal
             │
   ┌─────────▼─────────┐   stdin: commands      ┌─────────────────────┐
   │ Service.qml       │ ─────────────────────▶ │ omakodi daemon      │── HTTP 8080 ──▶ Kodi
   │ shared state, IPC │ ◀───────────────────── │ (Python, stdlib)    │◀─ TCP 9090 ───  events
   └───┬──────────┬────┘   stdout: JSON lines   └─────────────────────┘
       │          │
 BarWidget.qml  Panel.qml (the remote)
```

- **`bin/omakodi`** is the only code that talks to Kodi. It runs Python 3 with
  the standard library only (`python` is a dependency of the `omarchy`
  package). Subcommands work without the shell, so every network behaviour can
  be tested from a terminal or over ssh.
- **Service** (`service` kind): starts `omakodi daemon` once, keeps the shared
  state (reachable, now playing, last error), and owns the IPC target. It
  restarts the daemon with a backoff if it exits.
- **Bar widget** (`bar-widget` kind): one per monitor, reads the service.
- **Panel** (`panel` kind): the remote. A separate panel rather than a popup
  of the bar icon, because the keybinding must open it while the icon is
  hidden. It opens on the focused monitor.

## Configuration and credentials

`~/.config/omakodi/config.json`, one Kodi box:

```json
{
  "host": "kodi.example.lan",
  "httpPort": 8080,
  "tcpPort": 9090,
  "username": "kodi",
  "password": "example-password",
  "youtubeMode": "smart"
}
```

or several (see "Kodi boxes"), each with its own id, login, ports, `mac`
and `wakeOnLan`:

```json
{
  "youtubeMode": "smart",
  "boxes": [
    {"id": "0b6f3c1e-8d2a-4c7b-9e15-3a4f6d8b2c90", "name": "Living room", "host": "kodi.example.lan",
     "username": "kodi", "password": "example-password"},
    {"id": "5d2e9a47-1c3b-4f86-a0d7-e8b4c6f13a25", "name": "Bedroom", "host": "bedroom.example.lan",
     "httpPort": 8081, "wakeOnLan": false}
  ]
}
```

- `host` is required. Ports default to 8080 and 9090; `eventPort`, Kodi's
  EventServer (see "Power"), to 9777. `username` and
  `password` may be left out when Kodi's web server has no login.
- The first form is one box (omakodi 0.2's file, still read as it is);
  the second a list of up to 32. A file with both `host` and `boxes` is a
  `bad config`. `id` (letters, digits, `-` and `_`, at most 64; omakodi
  makes a random UUID) is what the box's settings and state are kept
  under (see "Kodi boxes"); two boxes with one `id` are a `bad config`,
  two on one `host` are not. A box without an `id` (a file from before
  ids, or written by hand) goes by its `host` until it gets one, so two
  of those on one `host` (any case) are a `bad config`. `name` (one line,
  at most 100 characters) is what the remote calls the box; without one,
  its `host`. A box's `youtubeMode` overrides the top-level one.
  `boxes: []` is `not configured`.
- Optional, for Wake-on-LAN (see "Power"): `mac`, the box's MAC address
  (`aa:bb:cc:dd:ee:ff` or with `-`), which overrides the one the daemon
  read from Kodi; `wakeOnLan: false` turns waking off (no "Wake Kodi" in
  the remote, the MAC isn't read), for a box that can't be woken (a
  Raspberry Pi). A `mac` that is text but not a box's MAC address doesn't
  break the config, as on a phone remote: the box works, the text is kept
  as written (`omakodi config` adds "(not a MAC address)", the editor shows
  it), and waking says `Invalid MAC address for <box>`. A `mac` that isn't
  text is a `bad config`.
- The file must be owned by the user and not readable by group or others when
  any box in it holds a password. Otherwise `omakodi` refuses it with
  `config readable by others` and the fix (`chmod 600`).
- The password never appears in argv, `shell.json`, the daemon's output,
  error messages or logs. Kodi's own replies can contain secrets (a stream
  URL from a media-server add-on can carry an API key), so the stream `file`
  of the playing item is never emitted.
- Plugin settings that hold no secrets go in the bar widget's `shell.json`
  schema: `maxTitleLength`.
- **The YouTube mode is chosen in the remote** (its Settings, below), per
  box, like a phone remote's settings: kept in
  `~/.local/state/omakodi/youtube-mode.json` (`{"boxes": {"<id>":
  "youtube-first"}}`, mode 600; see "Kodi boxes") for
  the box in use, and read by every `omakodi` process (the play
  keybindings' included) for each play or queue. Until one is chosen for
  the box, the config file's `youtubeMode` (default `smart`). `omakodi config` shows
  the mode in use and where it came from.

Kodi setup, documented in the README: Settings → Services → Control → *Allow
remote control via HTTP* and *Allow remote control from applications on other
systems* (the second opens the event port 9090). For links: the SendToKodi
add-on, and optionally the YouTube add-on.

## Talking to Kodi

- **Commands:** JSON-RPC 2.0 over HTTP, `POST http://<host>:<httpPort>/jsonrpc`,
  Basic auth when configured. Connect timeout 4 s, read timeout 10 s.
- **Events:** Kodi's TCP JSON-RPC on `<tcpPort>`, which pushes notifications
  (`Player.OnPlay`, `Player.OnAVStart`, `Player.OnStop`, `Input.OnInputRequested`,
  …) without a login. Messages are concatenated JSON objects with no
  delimiter, so the reader splits them by brace depth outside strings.
  Keep-alive: `JSONRPC.Ping` after 30 s of silence, reconnect when no answer
  in 10 s, reconnect backoff 1 s doubling to 10 s.
- Kodi talks plain HTTP. The README says so: the password crosses the LAN
  unencrypted, and port 9090 has no login at all. That is Kodi's design, not
  something omakodi can fix.

### Errors

Every failure has one wording and one exit code. The daemon reports it as
`error`. What the user reads is the phone remote's message for it where
"Messages" has one (`wrong username or password` is `Wrong username or
password for <box>`), with the rest of the wording, the fix, under it in
the terminal and the top bar; the others as below.

| Error | Meaning | Exit |
| --- | --- | --- |
| `not configured` | No config file | 3 |
| `bad config` | Not JSON, or `host` missing, or a wrong type | 3 |
| `config readable by others` | Holds a password and mode allows group/other | 3 |
| `not reachable` | Connect failed or timed out (away from home?) | 4 |
| `bad address` | The box's address can't be one: not an IP address, nor a name of dot-separated labels (letters, digits, `_`, inner `-`; 63 characters each, 253 in all), e.g. `kodi..lan` or one with a port in it; nothing is sent | 3 |
| `wrong username or password` | HTTP 401 | 5 |
| `http <code>` | Any other non-200 | 1 |
| `bad response` | Not JSON-RPC | 1 |
| `kodi error: <message>` | JSON-RPC `error` member | 1 |
| `Nothing is playing` | A player command with no active player | 1 |
| `no link found` | `play`/`queue` text had no http(s) URL | 2 |
| `Nothing to send` | `play`/`queue` text, or the clipboard, is empty or only spaces | 2 |
| `can't read the clipboard` | `wl-paste` isn't there | 2 |
| `SendToKodi isn't installed on <box>` | Needed add-on missing or disabled | 1 |
| `Neither the YouTube add-on nor SendToKodi is installed on <box>` | A YouTube link and neither add-on | 1 |
| `SendToKodi couldn't play it on <box>` | SendToKodi gave up on the link (see "Sending a link") | 1 |
| `can't reach Kodi's EventServer` | The EventServer packet couldn't be sent (the name doesn't resolve, no network) | 4 |
| `No MAC address saved for <box>. Connect once while it's on, or add it in the box's settings.` | Waking with no MAC address known | 1 |
| `Invalid MAC address for <box>` | Waking with a MAC address that isn't a box's: the config's `mac` (`mac.json` keeps only valid ones) | 1 |
| `can't wake Kodi` | `wakeOnLan` is false, or the packet couldn't be sent | 1 |
| `that button sends a link` | A shortcut button that is Send a link was asked to open on Kodi | 2 |
| `not a Kodi path or add-on` | A typed shortcut path that is neither (see "Shortcut buttons") | 2 |
| `no such box` | `omakodi box` or the remote named a box the config doesn't have | 2 |
| `bad address`, `bad port`, `bad MAC address`, `bad username`, `bad password` | A box's settings the editor can't save (see "Kodi boxes"); this `bad address` is the same check as the one above, and keeps its words | 2 |
| `can't save`, `can't delete` | The config couldn't be written: a box with that address exists, the box is gone, or the file doesn't parse (3: fix it first) | 1 or 3 |
| `can't search the network` | No `avahi-browse`, the avahi daemon isn't running, or it took over 10 s | 1 |
| usage errors | Bad arguments | 2 |

`<box>` is the box in use's name (see "Messages").

## Sending a link

`omakodi play [--clipboard | TEXT]` and `omakodi queue [--clipboard | TEXT]`.
`--clipboard` reads `wl-paste --no-newline` (so a keybinding needs no shell
quoting). `--notify` reports the result as a desktop notification as well.

1. Take the first `http(s)://` URL in the text, trimming trailing `.,;!)`.
2. **YouTube video?** Hosts `youtube.com`, `www.`, `m.`, `music.`,
   `youtube-nocookie.com`, `youtu.be`; paths `/watch?v=ID`, `/shorts/ID`,
   `/live/ID`, `/embed/ID`, `/v/ID`, `youtu.be/ID`; ID is 11 of `[A-Za-z0-9_-]`.
   Playlists and channels are not single videos and go to SendToKodi.
3. **Route**, by the YouTube mode (chosen in the remote, else the config
   file's `youtubeMode`; see "Configuration and credentials"):

   | Mode | YouTube link goes to |
   | --- | --- |
   | `smart` (default) | YouTube add-on with fallback, but SendToKodi for 30 min after the add-on failed |
   | `youtube-first` | YouTube add-on, SendToKodi when it fails |
   | `youtube-only` | YouTube add-on, no fallback |
   | `sendtokodi-only` | SendToKodi |

   A missing YouTube add-on is common, so `smart` and `youtube-first` use
   SendToKodi without comment; the explicit modes (`youtube-only`,
   `sendtokodi-only`) fall through to the other add-on with a note in the
   message, as does `smart` after a recent failure. Neither installed → error. Non-YouTube links always go to
   SendToKodi (`Addons.GetAddonDetails` checks it is installed and enabled).
4. Item paths: `plugin://plugin.video.youtube/play/?video_id=<ID>` and
   `plugin://plugin.video.sendtokodi/?url=<url-encoded URL>` (the form
   SendToKodi's README documents for JSON-RPC).
5. **Play**. While Kodi plays from its video queue (`Player.GetProperties`
   `playlistid` 1, `position` n), `Playlist.Insert` the item at n + 1 and
   `Player.Open` that position, so the rest of the queue follows; otherwise
   `Player.Open` the item. With the YouTube add-on and a fallback, watch for
   a verdict for up to 30 s, listening on the event port *before* opening:
   - **failed:** the add-on's `Other.playback_failed` for this video ID; or
     `Player.OnStop` for the new item (not `end: true`) before it played; or
     the picture came up (`Player.OnAVStart`) but the play time hasn't moved
     for 12 s.
   - **playing:** the play time of the new item moved forward 3 s (also
     polled each second, in case the event port is closed), or the viewer
     paused, resumed or seeked the new item.
   - **undecided** after 30 s: leave it; Kodi shows its own error if it fails.
   - The old video keeps playing while the new one loads, so "new item" means
     a different `file|label` from before, or the same one restarted. In the
     queue it also means the item at n + 1: a failed queue item makes Kodi
     go on to the next one, which isn't the new video.

   - **stopped:** the user stopped it through omakodi (below): no
     fallback, no `smart` record, the message `Stopped on <box>`.

   A `stop` sent through omakodi (the remote's `x`, `omakodi control
   stop`, IPC) writes the time to `~/.local/state/omakodi/stopped` before
   it goes to Kodi, because the watch may run in another process (the
   keybinding's `omakodi play`). A watch that sees a stop noted after it
   opened the item (on a `Player.OnStop`, and at each poll) decides
   "stopped". A stop from Kodi's own remote can't be told apart from a
   failure.

   The stop note names the box it went to (`<time> <host>`); a watch
   counts only a stop to its own box (a note without a host, from omakodi
   0.2, counts for any).

   On failure: record the time for `smart` mode (per box, in
   `youtube-failed.json`: `{"hosts": {"kodi.example.lan": <time>}}`; the
   add-on is the box's), say "YouTube add-on couldn't
   play it, trying SendToKodi…" (progress), and open the SendToKodi path. On success
   clear the record. In the queue the SendToKodi item takes the failed item's
   place (`Playlist.Remove`; right after it if Kodi won't remove it).
6. **SendToKodi is watched too**, whenever `play` opens a SendToKodi item
   (the route, or the fallback above). When yt-dlp can't play a link
   (removed, login wall), Kodi sends no event at all; only its busy
   dialog tells (checked live): Kodi's `busydialog` (or
   `busydialognocancel`, `progressdialog`, `extendedprogressdialog`) shows
   while SendToKodi works, then either the new item plays or the dialogs
   close, a notification shows on the TV, and nothing plays. Listening on
   the event port before opening, polling `XBMC.GetInfoBooleans` and the player every 0.5 s for up
   to 60 s:
   - **playing:** the new item is in the player (a different `file|label`
     from before, or at the queue slot), or `Player.OnAVStart` after its
     `Player.OnPlay`.
   - **failed:** `Player.OnStop` of the new item before its picture came
     up; or the busy dialog was seen, then has been gone for 3 s with no
     new item (the dialog can blink off for half a second between steps).
   - **undecided** after 60 s (still busy, or never busy).
   - **stopped:** as in step 5: `Stopped on <box>`, no error.

   Messages: playing `Playing on <box>` (plus the route note); failed the
   error `SendToKodi couldn't play it on <box>: the TV shows why`;
   undecided `SendToKodi is still opening it on <box>`.
7. **Queue**: if nothing plays (`Player.GetActivePlayers` empty), play
   instead. Otherwise `Playlist.Add` to the video playlist (id 1) and report
   the queue length. No fallback, since it plays later.

Messages (see "Messages"): `Playing on <box>…` as `progress` once the
add-on is chosen, as the phone remote says it at once (and as the result
when nothing watches it), `Playing on <box>` once it is known to play,
`YouTube is still loading on <box>` when the YouTube add-on is undecided,
`Queued on <box> (3 in queue)`, plus the route note when the usual add-on
wasn't used (`Playing on <box> with SendToKodi (the YouTube add-on failed
recently)…`; after a fallback `Playing on <box> with SendToKodi (the
YouTube add-on couldn't play it)`).

## Messages

What omakodi says is worded as the phone remote says it, naming the box
in use: `<box>` is its `name`, which is its `host` when it has none
("Kodi" when not even that is known). The remote shows these as its short
message (see "Remote panel"), and `play` and `queue --notify` (the
keybindings) as their notification, in the same words.

| When | Message |
| --- | --- |
| A key or command and Kodi doesn't answer (`not reachable`); in the remote also a key pressed while it shows Offline, which isn't sent (see "Remote panel") | `Can't reach <box>` (an error) |
| A player key, or `a` (the audio key), with nothing playing | `Nothing is playing` (an error) |
| Wake up | `Wake-up sent to <box>` |
| Turn on soundbar | `Soundbar wake-up sent to <box>` |
| A play starts | `Playing on <box>…` |
| A queued link | `Queued on <box> (3 in queue)` |
| The YouTube add-on is still at it after 30 s | `YouTube is still loading on <box>` |
| The YouTube add-on failed | `YouTube add-on couldn't play it, trying SendToKodi…` |
| SendToKodi missing | `SendToKodi isn't installed on <box>` (an error) |
| Neither add-on, for a YouTube link | `Neither the YouTube add-on nor SendToKodi is installed on <box>` (an error) |
| Played or queued with the add-on the box's YouTube mode didn't ask for | the message ends ` with SendToKodi (<why>)` or ` with the YouTube add-on (<why>)` (see "Sending a link") |
| Wake up with no MAC address known | `No MAC address saved for <box>. Connect once while it's on, or add it in the box's settings.` (an error) |
| Wake up with a MAC address that isn't one | `Invalid MAC address for <box>` (an error) |
| Turn on soundbar, and the packet can't be sent | `Couldn't reach <box>: <why>`, `<why>` the system's reason (`Network is unreachable`) (an error) |
| `play` / `queue` text without a link (`no link found`) | `No link found` (an error) |
| `play` / `queue` with an empty clipboard, or text that is empty or only spaces | `Nothing to send` (in the remote a note, not an error) |
| `a` while something plays and Kodi lists no audio streams | `No audio streams to choose from` (a note) |
| Kodi says HTTP 401 (`wrong username or password`) | `Wrong username or password for <box>` (an error) |
| Kodi answers another HTTP status (`http <code>`) | `<box> answered HTTP <code>` (an error) |
| The box's address can't be one (`bad address`) | `Bad address for <box>` (an error) |
| Kodi's answer isn't JSON-RPC (`bad response`) | `Unexpected reply from <box>` (an error) |

A name that doesn't resolve is `Can't reach <box>`, as on the phone; the
fix under it says so. The phone remote also says "No link found in what
was shared" for its share menu; omakodi has no share menu, so it says `No
link found`.

omakodi's own, in the same words: `SendToKodi couldn't play it on <box>:
the TV shows why` (an error) and `SendToKodi is still opening it on
<box>` (step 6), and `Stopped on <box>` for a stop the user sent while a
play was watched (step 5).

- The daemon's results, the remote's short message and `--notify`'s
  notification have the message alone. The state's `error` is the
  message, then a newline and the fix (the error's wording after its
  kind, as in "Errors": `Wrong username or password for Living
  room\nKodi refused the login; check username and password in …`); the
  top bar shows the message under Offline and the fix under that, the bar
  widget's tooltip both. The CLI prints `omakodi: <message>` on stderr
  and the fix indented on the next line. An error with no message of its
  own (`kodi error: …`, `bad config: …`) is shown as it is, nothing under
  it. The box is the one in use, else the one the error came from (Kodi's
  errors carry the box's name), else "Kodi".
- Test connection (see "Kodi boxes") says Kodi's errors in the same
  words, as the phone remote's box screen does, with `<box>` the editor's
  Name, else its address: the message alone, no fix under it.
- A play with `--notify` shows one notification and updates it
  (`notify-send --print-id`, then `--replace-id`): `Playing on <box>…`
  becomes `Playing on <box>`, or the error.

## Remote commands

`omakodi control <action>`:

| Action | Kodi call |
| --- | --- |
| `up` `down` `left` `right` | `Input.Up` … ; during plain fullscreen video: `Input.ExecuteAction` `chapterorbigstepforward` / `chapterorbigstepback` / `stepback` / `stepforward` |
| `select` | `Input.Select`; during fullscreen video: `Input.ShowOSD` |
| `back` `info` `context` `osd` | `Input.Back`, `Input.Info`, `Input.ContextMenu`, `Input.ShowOSD` |
| `home` | `GUI.ActivateWindow` `home` |
| `playpause` `stop` | `Player.PlayPause`, `Player.Stop` on the active player |
| `next` `previous` | `Player.GoTo` `next` / `previous` on the active player (the queue) |
| `rewind` `fastforward` | `Player.SetSpeed` `decrement` / `increment` (Kodi's rewind and fast-forward: each press steps the speed) |
| `volup` `voldown` | Kodi's own volume a step up / down (Kodi's "volume steps" setting): `Application.GetProperties` `volume`, then `Application.SetVolume` with the number (0 to 100); see "Volume" |
| `mute` | Kodi's own mute on / off: `Application.SetMute` `true` / `false` from `muted` |
| `soundbarup` `soundbardown` | Kodi's volume keys, `Application.SetVolume` `increment` / `decrement`: with HDMI-CEC volume control they go to the TV or soundbar; see "Volume" |
| `fullscreen` | `GUI.SetFullscreen` `toggle` |
| `powermenu` | `GUI.ActivateWindow` `shutdownmenu` (Kodi's own power menu on the TV) |
| `reboot` `shutdown` | `System.Reboot`, `System.Shutdown`, only when `System.GetProperties` `canreboot` / `canshutdown` is true (else `Kodi can't reboot` / `Kodi can't shut down`); see "Power" |
| `soundbaron` | Kodi's builtin `CECActivateSource` through the EventServer (UDP), not JSON-RPC: Kodi becomes the active HDMI source, which wakes the soundbar (with Kodi's CEC setting *Force AVR to wake up when Kodi is activated*); see "Power" |
| `playerinfo` | `Input.ExecuteAction` `playerprocessinfo` (Kodi's player process info on the TV: codecs, resolution, dropped frames; again closes it) |

"Plain fullscreen video" = `Window.IsActive(fullscreenvideo)` and no modal
dialog and no OSD (`XBMC.GetInfoBooleans`), cached briefly so arrow keys stay
fast. `omakodi status` prints the now-playing JSON (below) once.

`omakodi seek POSITION` (seconds, `MM:SS` or `H:MM:SS` from the start, at
most 7 days) → `Player.Seek` with `{"time": …}` on the active player.

`omakodi audio INDEX` plays the audio track with that `index` (see "Audio
tracks"); `omakodi status` lists them.

`omakodi wake` sends the Wake-on-LAN packet (see "Power").

`omakodi volume LEVEL` sets Kodi's own volume, 0 to 100
(`Application.SetVolume` with the number; see "Volume").

`omakodi shortcut BUTTON` opens the remote's shortcut button BUTTON (1 to
5, from the left) of the box in use on Kodi (see "Shortcut buttons");
Send a link is refused (`that button sends a link`, exit 2).

`omakodi boxes` lists the config's boxes (`* Living room
(kodi.example.lan:8080)`, `*` for the one in use); `omakodi box BOX`
switches to the box with that id, else the first with that `host`, else that name (any case), for
the remote, the bar and the keybindings too; `omakodi box` prints the one
in use (see "Kodi boxes"). Every other command acts on the box in use;
`omakodi config` shows it, with the names of all boxes.

## Daemon protocol

`omakodi daemon` runs until stdin closes. One JSON object per line each way.

In (from the service):

```json
{"id": 7, "cmd": "control", "action": "up"}
{"id": 12, "cmd": "control", "action": "right", "repeat": true}
{"id": 8, "cmd": "play", "text": "https://…"}
{"id": 9, "cmd": "queue", "text": "https://…"}
{"id": 10, "cmd": "refresh"}
{"id": 11, "cmd": "text", "text": "the wire", "done": false}
{"id": 13, "cmd": "seek", "seconds": 754}
{"id": 14, "cmd": "goto", "position": 2}
{"id": 15, "cmd": "remove", "position": 4}
{"id": 16, "cmd": "audio", "index": 1}
{"id": 17, "cmd": "wake"}
{"id": 18, "cmd": "volume", "level": 60}
{"id": 19, "cmd": "youtubeMode", "mode": "youtube-first"}
{"id": 20, "cmd": "youtubeRetry"}
{"id": 21, "cmd": "shortcut", "slot": 1}
{"id": 22, "cmd": "shortcutSet", "slot": 1, "pick": {"seq": 5, "index": 3}}
{"id": 23, "cmd": "shortcutSet", "slot": 1, "path": "plugin://plugin.video.youtube"}
{"id": 24, "cmd": "shortcutSet", "slot": 1, "sendLink": true}
{"id": 25, "cmd": "shortcutSet", "slot": 1, "icon": "movie"}
{"id": 26, "cmd": "shortcutSet", "slot": 1, "reset": true}
{"id": 27, "cmd": "browse", "action": "root"}
{"id": 28, "cmd": "browse", "action": "open", "seq": 5, "index": 2}
{"id": 29, "cmd": "browse", "action": "back", "seq": 6}
{"id": 30, "cmd": "browse", "action": "reload", "seq": 6}
{"id": 31, "cmd": "box", "key": "5d2e9a47-1c3b-4f86-a0d7-e8b4c6f13a25"}
{"id": 32, "cmd": "boxSave", "key": "", "box": {"name": "Bedroom", "host": "bedroom.example.lan", "httpPort": 8080, "tcpPort": 9090, "username": "kodi", "password": "…", "mac": ""}}
{"id": 33, "cmd": "boxTest", "key": "0b6f3c1e-8d2a-4c7b-9e15-3a4f6d8b2c90", "box": {"host": "kodi.example.lan", "httpPort": 8080, "tcpPort": 9090, "username": "kodi"}}
{"id": 34, "cmd": "boxDelete", "key": "5d2e9a47-1c3b-4f86-a0d7-e8b4c6f13a25"}
{"id": 35, "cmd": "discover"}
{"id": 36, "cmd": "keyboard"}
```

Out:

```json
{"type": "state", "reachable": true, "error": "", "playing": {"title": "…", "subtitle": "…", "kind": "video", "paused": false, "speed": 1, "positionSec": 393, "durationSec": 3009, "art": ""}, "volume": 80, "muted": false, "queue": null, "details": null, "audio": null, "power": null, "wake": false, "wakeOnLan": true, "volumeKeys": "unknown", "youtube": {"mode": "smart", "from": "config", "avoidUntil": 0, "box": "0b6f3c1e-8d2a-4c7b-9e15-3a4f6d8b2c90"}, "shortcuts": {"box": "0b6f3c1e-8d2a-4c7b-9e15-3a4f6d8b2c90", "buttons": [{"label": "Home", "sendLink": false, "icon": "", "art": "", "auto": "home", "custom": false, "typed": ""}, …]}, "input": null, "boxes": {"current": "0b6f3c1e-8d2a-4c7b-9e15-3a4f6d8b2c90", "list": [{"id": "0b6f3c1e-8d2a-4c7b-9e15-3a4f6d8b2c90", "name": "Living room", "host": "kodi.example.lan", "httpPort": 8080, "tcpPort": 9090, "username": "kodi", "hasPassword": true, "mac": "", "knownMac": "aa:bb:cc:dd:ee:ff"}]}, "connecting": false}
{"type": "picker", "seq": 6, "title": "YouTube", "crumb": "YouTube", "folder": true, "depth": 3, "status": "ready", "error": "", "items": [{"label": "Trending", "detail": "", "browse": true}]}
{"type": "found", "status": "done", "error": "", "total": 2, "boxes": [{"name": "Bedroom", "host": "192.0.2.20", "httpPort": 8080, "tcpPort": 9090}]}
{"type": "boxTest", "id": 33, "name": "Living room", "mac": "aa:bb:cc:dd:ee:ff"}
{"type": "progress", "id": 8, "message": "Playing on Living room…"}
{"type": "progress", "id": 8, "message": "YouTube add-on couldn't play it, trying SendToKodi…"}
{"type": "result", "id": 8, "ok": true, "message": "Playing on Living room with SendToKodi (the YouTube add-on couldn't play it)"}
{"type": "result", "id": 7, "ok": false, "error": "Can't reach Living room"}
```

- `id` is a number or text of up to 64 characters, echoed in the result.
  Every command gets exactly one `result`; `play` and `queue` may send
  `progress` lines before it. `message` is `""` when there is nothing to say.
- Remote actions run in order on one worker, `play`/`queue` on another, so a
  play waiting 30 s for the YouTube verdict never holds up the arrow keys. A
  remote action that waited over 3 s behind a slow one is skipped
  (`skipped: Kodi was busy with the previous key`), so held keys don't replay
  late.
- `repeat: true` marks a held key's repeat. A repeat of `up` `down` `left`
  `right` during plain fullscreen video is dropped (`ok`, empty message):
  there each press skips (Left/Right a small step, about 10 s; Up/Down
  Kodi's big step, up to 10 minutes), so a held arrow skips once. Elsewhere
  it is sent like a press. Missing means false.
- `speed` is Kodi's play speed: 1 normal, 0 paused, 2, 4, … fast-forward,
  -2, -4, … rewind (bounded to ±64; anything else reads as 1).
- `art` is a local image file of what plays, or `""` (see "Artwork").
- `queue` is the video queue while it plays, else `null` (see "The queue").
  `goto` plays the entry at `position`, `remove` takes it out; both run in
  line with the remote actions.
- `details` is what Kodi knows about the playing item, or `null` (see
  "Details").
- `audio` is the playing item's audio tracks, or `null` (see "Audio
  tracks"). The `audio` command runs in line with the remote actions.
- `power` is what Kodi allows and whether it is on, off or restarting, or
  `null` before Kodi has said (see "Power").
- `volume` and `muted` are Kodi's own. `volumeKeys` says where Kodi's
  volume keys (`soundbarup`, `soundbardown`) go: `"kodi"`
  (Kodi's own volume), `"tv"` (over HDMI-CEC to the TV or soundbar) or
  `"unknown"` (see "Volume"). The
  `volume` command sets Kodi's own volume (`level` 0 to 100), in line with
  the remote actions.
- `youtube` is the YouTube mode in use (`mode`), where it came from
  (`"remote"`: chosen in the remote, `"config"`: the config file) and, in
  `smart` mode, until when SendToKodi is used after the add-on failed
  (`avoidUntil`, Unix seconds; 0 when it isn't), and the box it is for
  (`box`, the box in use's id). It is there whatever Kodi
  answers: the choice doesn't need Kodi. `youtubeMode` saves a mode for the
  box; `youtubeRetry` forgets the add-on's failure, so the next YouTube
  link tries it again. Both run in line with the remote actions.
- `boxes` is the config's boxes, each with its `id`, and the one in use
  (`current`, its id), with what the remote's editor shows: never a password, only
  `hasPassword`; `mac` is the config's, `knownMac` the one read from Kodi
  (see "Kodi boxes"). `connecting` is true from a switch to another box
  until that box answered or failed once. `box` switches to the box
  whose id is `key`, `boxSave` adds a box (`key` `""`) or changes the one
  whose id is `key`, `boxDelete` takes the one whose id is `key` out; all
  three in line with the remote actions. (`box` and `boxDelete` with a
  `host` instead, and a `key` that is a box's `host`, are a shell from
  before ids: the first box at that address.) `boxTest` asks the box in `box` who it is, on a worker
  of its own (a box that isn't there takes 4 s): a `boxTest` line with
  Kodi's name and MAC address (`""` when it doesn't say), then the result
  (`✓ Kodi 21.3`, or the error). `discover` searches the network on a
  worker of its own: a `found` line with `"status": "searching"`, then
  `"done"` with the boxes found that aren't saved (and `total`, all it
  found) or `"failed"` with the `error`, then the result. A `found` line
  is sent again after `boxSave` and `boxDelete`.
- `shortcuts` is the box in use's five shortcut buttons (see "Shortcut
  buttons"), there whatever Kodi answers: `label`; `sendLink` for Send a
  link; `icon`, the built-in icon chosen for it or `""`; `art`, a local
  image of Kodi's art for it or `""` (as `playing.art`); `auto`, the
  built-in icon that matches what it opens; `custom`, false while it is the
  default; `typed`, the path when it was typed (to edit it again), else
  `""`. Paths and Kodi's art URLs are never in the state.
- `shortcut` opens button `slot` (0 to 4) on Kodi; `shortcutSet` changes
  it, with exactly one of: `pick` (a row of the picker's page `seq`, or
  `index` -1 for "Use this folder"), `path` (typed; `""` resets), `sendLink:
  true`, `icon` (a built-in icon's name, or `""` for Kodi's art or the
  automatic one), `reset: true`. Both run in line with the remote actions.
- `browse` moves the "Choose from Kodi" picker: `root` starts it at its
  first page, `open` goes into row `index` of page `seq`, `back` goes up
  (the first page stays), `reload` asks Kodi again. It runs on a worker of
  its own (a folder can take 45 s while an add-on runs on the box), so keys
  and plays never wait for it. Each step sends the page as a `picker` line:
  first `"status": "loading"` while Kodi is asked, then `"ready"` with its
  rows or `"failed"` with the `error`; then the `result` (an error when the
  page couldn't be listed). `seq` grows with every page sent; `open`,
  `back`, `reload` and a `pick` naming an older `seq` are refused (`the list
  changed: look again`) and the page shown now is sent again. `depth` is 1
  on the first page; `folder` is true on a page "Use this folder" can pick.
  Rows have `label` and `detail` (150 characters of plain text) and
  `browse` (opens a page rather than being picked); at most 500.
- `wake` is true when `wake` can wake the box: a MAC address is known and
  `wakeOnLan` isn't false; `wakeOnLan` is the config's (true without one),
  so the remote hides Wake up only when it is false. `wake` runs in line
  with the remote actions.
- `seek` runs in line with the remote actions; `seconds` is a whole number
  from 0 to 7 days.
- `input` is set while Kodi's on-screen keyboard is open (event
  `Input.OnInputRequested`): `{"type": "keyboard", "title": "Search",
  "value": ""}`; `value` is always `""` for the password types. It goes back
  to `null` on `Input.OnInputFinished` or when the event port reconnects.
  `text` sends `Input.SendText` (`done: true` submits it). `keyboard` is
  the remote's keyboard key (Type text), in line with the remote actions:
  with `input` set it does nothing; else it asks Kodi whether its keyboard
  is open (`XBMC.GetInfoBooleans` `Window.IsVisible(virtualkeyboard)`,
  `Window.IsVisible(numericinput)`; it opened before omakodi listened)
  and then sets `input` (`"keyboard"` or `"number"`, title and value
  `""`: Kodi's text isn't read, since for a password it would be the
  password), or answers with the message `Kodi isn't asking for text
  right now`. Found while the event port is closed, nothing will say when
  that keyboard closes (no `Input.OnInputFinished`), so `input` then
  carries `"recheck": true`: the remote's keyboard key sends `keyboard`
  again instead of opening the dialog at once, and `keyboard` asks Kodi
  again even with `input` set. Still open: the answer is `""` (the remote
  opens the dialog); gone: `input` goes back to `null` and the answer is
  `Kodi isn't asking for text right now`.
- State is pushed on change: first after start, on player, application and
  system events, and on a 5 s poll while something plays (positions move
  without events), while failing, or while the event port is closed; idle
  with the event port open, every 60 s. `refresh` pushes it even when
  unchanged, then answers. After a command that changes it (`playpause`,
  `stop`, `next`, `previous`, `rewind`, `fastforward`, `seek`, `audio`,
  volume, `mute`, `play`, `queue`) it is read again at once, and after
  `soundbarup`/`soundbardown` once more a second later (see "Volume").
- `reachable` turns false only after 45 s of continuous failure, so a short
  blip stays quiet; a success resets it. Until then the last state stands.
  Configuration errors and a wrong password show at once (with `reachable`
  false and true respectively); other Kodi errors keep `reachable` true.
- The config file is read again when it changes, so fixing it needs no
  restart of the shell; the same for `box.json` (`omakodi box` from a
  terminal switches the remote too, within a second).
- A line that isn't a valid command is answered with
  `{"type":"result","id":<id or null>,"ok":false,"error":"bad request: …"}`;
  lines over 16 KiB are dropped the same way. The daemon never exits on bad
  input; it exits when stdin closes.
- All strings are bounded (titles, messages and errors 300 chars) and emitted
  as data; the QML shows them as plain text (the one exception: the Details
  dialog's plot, with its web links and Kodi's bold, italics and colours,
  see "Details").

## Artwork

- The daemon asks `Player.GetItem` for `art` and `thumbnail` and picks the
  first `image://…` URL of `art.poster`, `art.tvshow.poster`, `art.thumb`,
  `art.album.thumb`, `art.icon`, `thumbnail` (at most 4096 characters).
- It fetches it on its own thread (state and keys never wait for it) from
  Kodi's `/image/<url-encoded art URL>`, with the login, at most 4 MB.
  Only JPEG, PNG and WebP are kept, recognised by their first bytes, not the
  name or Content-Type; anything else, a 404 or an oversized answer means
  no art.
- Files go to `$XDG_CACHE_HOME/omakodi/art/` (`~/.cache/…`; both folders
  700, files 600), named by the first 32 hex digits of the URL's SHA-256 plus
  the type's extension. The 60 most recently used are kept. An image already
  there is used without asking Kodi again.
- The cast's photos in "Details" (each cast member's `thumbnail`, an
  `image://…` URL) come the same way, on the same thread after what plays
  and the shortcut buttons' art, in order; each once per item (one Kodi
  hasn't got stays a person icon). The state is pushed again after the
  first six and at the end.
- The state carries only that local path (`playing.art`, a cast member's
  `photo`), once the file is
  there; the URL itself (it can carry a media server's API key) is never in
  the state, the logs, errors or file names. `Protocol.js` accepts only an
  absolute path to a 32-hex-digit `.jpg`/`.png`/`.webp` in an
  `omakodi/art/` folder.

## The queue

- While the active player plays from the video playlist (`playlistid` 1,
  read with the position in the same `Player.GetProperties` call as the
  time), the state carries `"queue": {"position": 3, "start": 0, "total":
  7, "items": [{"title": "…", "subtitle": "…"}]}`; otherwise `null`.
- `Playlist.GetProperties` `size` is read on each poll; the entries
  (`Playlist.GetItems`) only when the size or
  the playing position changed, or after a `Playlist.*` event (which also
  reads the state at once).
- At most 100 entries: the whole queue, or a window from 20 before the
  playing one. Their titles and subtitles are cut to 150 characters, so a
  full window stays far below the 64 KiB line limit. An answer that can't
  be used (an error, over 1 MB) gives no entries; only a lost connection or
  a wrong password fails the read.
- Titles for queued links: Kodi has no title for an add-on item until it
  plays (its label is the path's last part, "play"), and `Playlist.Add`
  can't give it one. So `queue`, before `Playlist.Add`, stores a title in
  `~/.local/state/omakodi/titles.json` (600; the 200 most recent; keys are
  the first 32 hex digits of the SHA-256 of the queued item's path): for a
  YouTube video, the `title` from `https://www.youtube.com/oembed?format=json&url=https://www.youtube.com/watch?v=<ID>`
  (HTTPS, 4 s timeout, at most 64 KB, User-Agent `omakodi`), else
  `YouTube video <ID>`; for other links, the link's host and path. Any
  failure there still queues the link.
- The queue read then also asks for each entry's `file`, only to look up
  that hash for entries whose `title` Kodi leaves empty; Kodi's own title
  wins once it has one. The file never leaves the daemon. The entries are
  read again when `titles.json` changes (`omakodi queue` from a keybinding
  runs outside the daemon).
- `goto` → `Player.GoTo` with the position; `remove` → `Playlist.Remove`.
  Both refuse unless the video queue plays (`not playing the queue`), a
  position past the end (`not in the queue: it changed; look again`), and
  `remove` the playing entry (`that one is playing: …`).

## Details

What the remote's Details dialog shows (as a phone remote's details
screen); all of it comes from Kodi, nothing is looked up online.

- The daemon reads them on a new item only, not on every poll: when the
  playing item's type, library id, label, title, show, season, episode,
  artist, album or art differ from the last read. It asks `Player.GetItem`
  for `title`, `showtitle`, `season`, `episode`, `artist`, `plot`,
  `plotoutline`, `tagline`, `genre`, `year`, `premiered`, `firstaired`,
  `studio`, `rating`, `votes`, `mpaa`, `runtime`, `director`, `writer`,
  `country`, `cast` and `streamdetails`; `Player.GetProperties` for
  `currentvideostream` and `currentaudiostream`; and `XBMC.GetInfoLabels`
  for the player's labels (`VideoPlayer.Plot`, `.Tagline`, `.Artist`,
  `.Genre`, `.Premiered`, `.Year`, `.Studio`, `.Rating`, `.Votes`,
  `.Director`, `.Writer`), which add-ons fill rather than the item: a label
  stands in for each field the item leaves empty. When the playing streams
  weren't known yet (an item that has only just started), it reads them
  once more after the next `Player.OnAVStart`.
- The state carries `"details": {"title": "…", "subtitle": "2019", "plot":
  "…", "plotStyles": [{"from": 0, "to": 15, "bold": true, "color":
  "#add8e6"}], "badges": ["4K", "HEVC", "Dolby Vision", "DD+", "5.1"], "info":
  [{"kind": "genre", "text": "Drama, Mystery"}, …], "cast": [{"name": "…",
  "role": "…", "photo": "/home/…/.cache/omakodi/art/<hash>.jpg"}]}`. Empty
  fields are left out; `null` while nothing plays or when Kodi knows
  nothing beyond the title (no plot, badges, info or cast).
- `title`: the item's title, else its label. `subtitle`: "S01E02 · Show"
  for an episode, the show, the year, else the artist (a YouTube video has
  a year, so its subtitle is the year, as on the phone).
- `plot`: the item's plot, else the `VideoPlayer.Plot` label, the plot
  outline, the tagline, the `VideoPlayer.Tagline` label. A YouTube
  description's stats line ("42K Views | 2.6K Likes | 371 Comments", in
  its first 4 lines) keeps only the views.
- `info`, in this order, each row only when Kodi has it (lists joined with
  ", ", a label's " / " too):
  `channel` (the artists, for everything but songs: the channel of an
  add-on video), `genre`, `show` (episodes only), `date` (first aired,
  else premiered, else the `Premiered` label, else the year, as Kodi writes
  them: "2019-03-01"), `studio`, `rating` (one decimal, "7.8 (12,345
  votes)" when Kodi counts votes), `age` (the MPAA rating without "Rated
  "), `runtime` (the item's, else the playing length: "1h 52m", "56m",
  "9m 57s" under ten minutes), `director`, `writer`, `country`.
- `cast`: up to 20, in Kodi's order (`order`), each with a name; `role`
  may be `""`. `photo` is a local file once fetched (see "Artwork"), else
  `""`; the photo's URL never leaves the daemon.
- Bounds: `title` 300 characters, `plot` 5000, cut with "…"; each info
  row 300; cast names and roles 60; `badges` at most 5 of 20;
  `plotStyles` at most 200 (the text after the 200th stays plain).
- Plain text: Kodi's formatting tags (`[B]`, `[I]`, `[LIGHT]`, `[COLOR …]`,
  `[UPPERCASE]`, `[LOWERCASE]`, `[CAPITALIZE]`, `[TABS]`, `[CR]`, any case,
  and their closing tags; `[COLOR …]` also written `[COLOR=…]` or
  `[COLORred]`) are taken out and `[CR]` becomes a line break; control
  characters go. Other brackets ("[2019]", "[Official Video]") are text, as
  Kodi shows them. The plot keeps its line breaks (no more than one empty
  line in a row); every other field is one line (a `[CR]` is a space) and
  plain.
- Bold, italics and colours: the plot shows Kodi's formatting as a phone
  remote does. `plotStyles` says where: each entry a stretch of `plot`
  (`from` to `to`, in UTF-16 units, as QML counts; in order, never
  overlapping) with `bold`, `italic` and `color` (`#rrggbb`), the ones
  that are false or empty left out. `[B]` is bold, `[I]` italic,
  `[COLOR x]` colours its text with `x`: a hex colour, `AARRGGBB` or
  `RRGGBB`, with an optional `#` or `0x` (the alpha is ignored: the text
  stays readable), or one of the common colour names (white, black, red,
  green, blue, yellow, orange, cyan, grey/gray, gold, lime, ghostwhite …;
  a fixed table in `details.py`, the basic ones as light as the phone
  shows them on a dark screen). An unknown colour leaves its text in the
  colour around it. A closing tag ends its own opening tag (the latest of
  that kind; one with nothing open does nothing); tags left open run to
  the end. `[LIGHT]`, `[UPPERCASE]`, `[LOWERCASE]`, `[CAPITALIZE]` and
  `[TABS]` go without an effect. The daemon reads the tags; the remote
  builds the markup itself (`<b>`, `<i>`, `<span style="color:#rrggbb">`
  around escaped text) and checks every colour again: nothing from Kodi
  is ever markup. A link takes the link colour, and bold or italics
  around it.
- Colours on the theme: Kodi's colours are made for a dark screen, so the
  remote checks each against the dialog's background (the theme's popup
  colour, as the card draws it) with WCAG's contrast ratio. One of 4.5:1
  or more (what WCAG asks of body text) is drawn as Kodi gave it, so a
  dark theme looks as the phone does. One below is darkened on a light
  background, or lightened on a dark one (towards black or white,
  whichever stands out more), only as far as it takes to reach 4.5:1,
  keeping its hue and saturation: white on a white theme becomes grey,
  light blue a darker blue. `PlotLinks.js` does it (`readable()`) when it
  builds the markup, so the result is again a `#rrggbb` the remote
  computed; a theme change while the remote is open redraws the plot in
  the new colours. The art never shows behind the plot: the now-playing
  page covers the remote's blurred art, and the Details dialog is opaque
  in the popup colour, so that colour is the only background to check
  against (a test holds the dialog to it; were the art ever let through,
  the colours would have to be checked against the popup colour blended
  with black and with white at the art's strength too). The link colour and the plot's own text colour are
  the theme's and stay as they are.
- Links: the remote shows the plot's web links as links, as a phone remote
  does (YouTube descriptions are full of them); everything else in the plot
  stays text. `PlotLinks.js` finds them: `http://` or `https://`
  (any case; no other scheme) with a host, up to a space or `<`, `>`, `"`,
  `'`, at most 4096 characters; a trailing `.` `,` `;` `:` `!` `?` `…` `*`
  is the sentence's, and so is a closing `)` `]` `}` without its opening one
  in the link. The rest of the plot is escaped before it becomes Qt rich
  text: the only markup is the remote's own (the links, as `<a href="N">`,
  N their number, never the URL; line breaks; bold, italics and colours
  from `plotStyles`). A link opens in the default
  browser with `xdg-open`, the URL its one argument (no shell), after the
  same check; nothing else ever opens. Kodi isn't asked to play it: the
  phone remote doesn't offer that either.
- Badges, in this order, as on the phone: the resolution from the playing
  video stream, else the library's `streamdetails` (Kodi's own steps: SD,
  720p, 1080p, 4K, 8K); the video codec (HEVC, H.264, AV1, VP9, VP8, MPEG-2,
  MPEG-4, VC-1, else in capitals); the HDR type (HDR10, HDR10+, Dolby
  Vision, HLG, else HDR); the audio codec (DD for AC3, DD+ for E-AC3, DD+
  Atmos, and the others by name: TrueHD, TrueHD Atmos, DTS, DTS-HD MA,
  DTS:X, AAC, FLAC, Opus, MP3, PCM …, an unknown codec in capitals, letters
  and digits only; the audio track list words codecs as Kodi does instead) and channels (Mono, 2.0, 5.1, 7.1, else `N ch`) from the playing
  audio stream, else `streamdetails`.
- An answer that can't be used (an error, over 1 MB) gives nothing from
  it; only a lost connection or a wrong password fails the read.

## Audio tracks

- Read on every poll in the same `Player.GetProperties` call as the time
  (`audiostreams`, `currentaudiostream`), so a track switched on the TV
  shows too.
- `"audio": {"current": 1, "tracks": [{"index": 0, "name": "…",
  "language": "eng", "codec": "AC3", "channels": "5.1"}]}`; `null` while
  nothing plays or Kodi lists no tracks. `current` is the `index` of the
  playing track, or -1 when that isn't one of the listed ones.
- Bounds: at most 32 tracks, `index` 0–999 (others are left out); `name`
  100 characters of plain text on one line (as in "Details": Kodi's tags
  taken out); `codec` as Kodi says it, in capitals, as a phone remote shows
  it (AC3, EAC3, TRUEHD, DTS, DTSHD_MA; letters, digits, `_` and `-` only,
  20 characters) and `channels` (mono, stereo, 5.1, 7.1, else `N ch`), or
  `""`. The badges in "Details" keep their own words (DD, DD+, TrueHD …).
- How a track reads, as on a phone remote: the language, then Kodi's name
  for the stream, joined with " · "; only when Kodi gives the stream no
  name, the codec and channels ("AC3 5.1") take its place; a part the same
  as one before it is left out. With none of these: "Audio N", N its place
  in the list from 1. So "English · Director's commentary", "Norwegian ·
  EAC3 5.1", "Audio 2".
- `language` is the English name of Kodi's code, from a table in the
  daemon of about 90 languages: ISO 639-1 (`en`), 639-2 (`eng`, and the
  older forms such as `ger`, `fre`), with a region kept in brackets
  (`pt-BR`, `pt_BR` → "Portuguese (BR)"; a script as written: "Chinese
  (Hant)"). An unknown code is shown as it is
  (up to 20 letters, digits and `-`); `und`, `unk`, `mul`, `zxx` and an
  empty code give `""`. At most 40 characters.
- `audio` → `Player.SetAudioStream` with `stream` the index. It refuses an
  index that isn't a whole number from 0 to 999 (`bad request`), nothing
  playing (`nothing playing`), and an index Kodi doesn't list now (`no such
  audio track: it changed; look again`).

## Volume

Two volumes: Kodi's own, and the TV's or soundbar's. Kodi's volume keys
(`Application.SetVolume` `increment`/`decrement`, `Application.SetMute`
`toggle`) go wherever Kodi sends them: with HDMI-CEC volume control on, to
the TV or soundbar, and Kodi's own volume stays where it is. A number
(`Application.SetVolume` 60) and a true/false mute always act on Kodi's own
(checked live: the sound went quieter and silent, Kodi's level and mute
flag moved). Kodi can't read the soundbar's level, so the soundbar gets
step keys, never a slider or a number.

- `volup`, `voldown`, `mute` (`+` `-` `m`) act on Kodi's own volume: a
  step and mute on or off. A step is 100 / Kodi's "volume steps" setting
  (`Settings.GetSettingValue` `audiooutput.volumesteps`, read once per
  box; 90 by default, so 1%) percent, at least 1; 5% when Kodi doesn't
  say. It goes from the level Kodi reports to the next one on the
  step's grid (97 up is 100, 97 down is 95 with 5% steps), within 0 to
  100.
- `soundbarup`, `soundbardown` (`0` `9`) send Kodi's volume keys. No
  soundbar mute: `m` mutes Kodi (the user's choice).
- Finding out where Kodi's volume keys go: after a `soundbarup` or
  `soundbardown` that Kodi answered, the daemon compares Kodi's volume
  from before the key with what Kodi says a second later. Changed:
  `"kodi"` (no CEC volume: the soundbar keys only repeat `+` `-`). The
  same, while it could have moved (below 100 for up, above 0 for down):
  `"tv"`. At the limit it learns nothing. A key pressed within that second
  starts the comparison again.
- What it learns is kept per box in `~/.local/state/omakodi/volume.json`
  (`{"hosts": {"kodi.example.lan": "tv"}}`, mode 600), so the remote
  knows after a restart; a later key that says otherwise replaces it.
  Until a key has said, `volumeKeys` is `"unknown"`.
- With audio passthrough, Kodi's own volume has no effect (the README
  says so).

## Power

- `System.GetProperties` `canreboot` and `canshutdown` are read once Kodi
  answers, and again each time it comes back after being off or
  restarting. The state carries `"power": {"state": "on", "reboot": true,
  "shutdown": true}`.
- `state` is `"off"` after a `shutdown` that Kodi answered, or Kodi's
  `System.OnQuit` with exit code 64; `"restarting"` after a `reboot`,
  `System.OnRestart` or `System.OnQuit` with any other code (LibreELEC and
  most boxes start Kodi again). From then `reachable` is false at once
  (no 45 s grace) and `error` is `""`, until Kodi answers again (`"on"`,
  capabilities read again). `"restarting"` with no answer for 3 minutes
  goes back to `"on"`, so a box that didn't come back reads as not
  reachable.
- The CLI and the IPC `control` run `reboot` and `shutdown` when asked;
  the remote asks again first (see "Remote panel").

### The soundbar over HDMI-CEC

- JSON-RPC can't run Kodi's builtins (`Input.ExecuteAction` takes only
  actions), so `soundbaron` sends one packet to Kodi's EventServer, UDP
  `<host>:<eventPort>` (9777), which Kodi opens with *Allow remote control
  from applications on other systems*: a `PT_ACTION` with the builtin
  `CECActivateSource`. It has no login; anyone who can reach that port can
  already send Kodi actions (README, SECURITY.md).
- The packet: the 32-byte header `XBMC`, version 2.0, type `0x000A`
  (`PT_ACTION`, big-endian 16 bits), sequence 1 and packet count 1 (32 bits
  each), the payload size (16 bits), client token 0 (32 bits: Kodi then
  tells clients apart by address) and 10 zero bytes; then the payload:
  `0x01` (run a builtin) and `CECActivateSource` ending in a zero byte. No
  `HELO` first: Kodi runs an action without one, and a `HELO` would show
  "new connection" on the TV.
- What it does is up to Kodi's CEC settings: Kodi becomes the active
  source, a TV that is on switches to Kodi, and with *Force AVR to wake up
  when Kodi is activated* the soundbar or AV receiver wakes. Whether a TV
  in standby comes on is the TV's choice; this is "turn on the
  soundbar", not "turn on the TV".
- UDP has no answer: the result says `Soundbar wake-up sent to <box>`
  whether or not anything listens. It only fails when the packet can't be
  sent (`can't reach Kodi's EventServer`): `Couldn't reach <box>: <why>`
  (see "Messages"). A box whose address can't be one (`bad address`) gets
  no packet.

### Wake-on-LAN

- While no MAC address is kept for the box, each time Kodi answers after
  the daemon starts, after it was off or restarting, or after the config
  changes, the daemon reads it (`XBMC.GetInfoLabels`
  `Network.MacAddress`). Kodi says `Busy` while it looks it up, so a reply
  that isn't a MAC address is asked again at the next read, up to 5
  times. A valid one is kept in `~/.local/state/omakodi/mac.json`
  (`{"boxes": {"<id>": "aa:bb:cc:dd:ee:ff"}}`, mode 600), per box (see
  "Kodi boxes"): filled in once, as on a phone remote, and kept after a
  change of the box's address.
- A MAC address is six hex pairs split by `:` or `-` (one kind), kept in
  lower case with `:`. All zeros and multicast addresses (lowest bit of the
  first byte set, so also `ff:ff:ff:ff:ff:ff`) aren't a box's and are
  refused.
- The config's `mac` wins over the saved one, even one that isn't a MAC
  address (then no MAC is read from Kodi, and waking says so, as on a
  phone remote); `wakeOnLan: false` turns all of it off.
- Waking sends the magic packet (6 bytes `ff`, then the MAC 16 times; 102
  bytes) three times over UDP to the broadcast address `255.255.255.255`
  port 9. It answers `Wake-up sent to <box>`. Kodi
  can't say whether the box got it: the state shows it once Kodi answers.
  With no MAC address known it says `No MAC address saved for <box>.
  Connect once while it's on, or add it in the box's settings.` (the
  editor's MAC address field, see "Kodi boxes"), and `Invalid MAC address
  for <box>` for one that isn't a box's (the config's `mac`; nothing is
  sent).
- The box must have Wake-on-LAN on and a wired connection (README).

## Shortcut buttons

A strip of five buttons under the remote's top bar, as on a phone remote:
**Home, Movies, TV shows, Music, Send a link** until they are changed. Any
of the five can be changed to one of Kodi's screens, a library section, an
add-on or one of its folders, a favourite or a source (picked from what
Kodi lists, live), a typed Kodi path or add-on, or Send a link, and given
another icon. They are kept per box.

- A button is `label`, `window` (Kodi's window name: letters, digits and
  `_`, at most 40), `path` (a folder to open, or an add-on id without
  `://` to start; at most 2048 characters, no control characters), `art`
  (Kodi's art for it, from the picker), `icon` (a built-in icon's name),
  `action` (`sendlink` for Send a link) and `typed`. Without a `window`,
  the path says: `plugin://plugin.audio.…`, `musicdb://` and
  `library://music…` open in `music`, `plugin://plugin.image.…` in
  `pictures`, `plugin://plugin.program.…` in `programs`, any other path in
  `videos`; no path at all is `home`.
- The defaults: Home (`home`), Movies (`videos`,
  `videodb://movies/titles/`), TV shows (`videos`,
  `videodb://tvshows/titles/`), Music (`music`), Send a link.
- **Opening** one: an add-on id → `Addons.ExecuteAddon` `{"addonid": …}`;
  a path → `GUI.ActivateWindow` `{"window": …, "parameters": [path,
  "return"]}`; no path → `GUI.ActivateWindow` `{"window": …}`. Send a link
  opens the remote's Send a link dialog instead; the daemon and the CLI
  refuse it (`that button sends a link`).
- **Kept** in `~/.local/state/omakodi/shortcuts.json` (600, folder 700) for
  each box's `id`: `{"boxes": {"<id>": [null, {…}, null, null, null]}}`, `null` for a button at its default (a default with only
  its icon changed is kept; set back to the automatic icon it is `null`
  again). The 32 most recently changed boxes are kept. Nothing in it is
  secret, but paths and art URLs stay in it and in the daemon.
- **Typed**: trimmed; `plugin://ID` gets a trailing `/`; any other text
  with `://` is kept as it is; an add-on id (letters, digits, `_`, then one
  or more `.` parts that may also have `-`) becomes `plugin://ID/` when it
  starts with `plugin.`, else stays (it is started, not opened). Anything
  else is refused (`not a Kodi path or add-on`, exit 2); an empty field
  resets the button. `Shortcuts.js` checks the same way, so Save is only
  offered for a path the daemon takes (a test runs both over the same texts).
- **The picker** ("Choose from Kodi"), a page at a time:
  - First page: Common; Video library; Music library; Video add-ons; Music
    add-ons; Picture add-ons; Program add-ons; Favourites; Video sources;
    Music sources.
  - Common: Kodi's windows Home, Movies, TV shows, Music videos, Music,
    Videos, Pictures, Live TV, TV guide, Radio, Weather, Favourites,
    Add-ons, Programs, File manager, Settings, System info.
  - Video library: Movies, Recently added movies, Movie genres, Movie sets,
    TV shows, Recently added episodes, In-progress TV shows, TV show
    genres, Music videos (`videodb://…`), and the folders Video playlists
    (`special://videoplaylists/`) and Library nodes (`library://video/`).
    Music library: Artists, Albums, Songs, Genres, Recently added albums,
    Recently played albums (`musicdb://…`), and the folders Music
    playlists and Library nodes.
  - Add-ons: `Addons.GetAddons` of that `content` (`video`, `audio`,
    `image`, `executable`), enabled, with `name` and `thumbnail`, sorted
    by name, `script.module.*` left out; the id is the row's detail. A
    `plugin.*` add-on opens as a folder (`plugin://ID/`); any other is
    picked (started).
  - Favourites: `Favourites.GetFavourites` with `window`,
    `windowparameter` and `thumbnail`; only those that open a window.
  - Sources: `Files.GetSources` (`video` or `music`), each a folder.
  - A folder: `Files.GetDirectory` (its `media`, `title` and `thumbnail`;
    up to 45 s, since it runs the add-on on the box): subfolders open as
    folders, smart playlists (`.xsp`) are picked, single files are left
    out. "Use this folder" picks the folder itself, labelled with the way
    there ("YouTube › Trending"), with its art, else its add-on's.
  - Labels are plain text (as in "Details").
- **Icons**: the chosen built-in icon; else Kodi's art for the button
  (`art`, else for a path in an add-on the add-on's `thumbnail` from
  `Addons.GetAddonDetails`, read once per box and add-on, which also names
  a typed add-on button), fetched as in "Artwork" (a path that isn't an
  `image://` URL is wrapped as one); else the built-in icon that matches
  it: Send a link a link, a smart playlist a playlist, an add-on path an
  add-on, Kodi's music videos, movies, TV shows and music sections their
  own, any other path a folder, and a window its own (home, music, videos,
  pictures, live TV, radio, weather, favourites, add-ons, programs, file
  manager, settings, system info). About 70 built-in icons (video, audio,
  pictures, lists, topics, Kodi and the box), by name in
  `lib/omakodi/shortcuts.py` and `Shortcuts.js` (a test keeps them equal);
  a saved name is never renamed. Art Kodi can't give is asked for again
  after a minute.

## Kodi boxes

The config can list several Kodi boxes (see "Configuration and
credentials"); omakodi follows one at a time, as a phone remote does.
**A box is known by its id**, as on a phone remote, not by its address:
two boxes on one address can both be saved, and a box keeps its settings
when its address changes.

- **The box in use** is kept in `~/.local/state/omakodi/box.json`
  (`{"id": "<id>"}`, mode 600): the box with that `id`, else (a file from
  before ids, `{"host": …}`) the first with that `host`, else the
  config's first. Every `omakodi` process reads it, so the bar, the
  remote, the play and queue keybindings and the CLI all act on the same
  box. It changes in the remote (below) or with `omakodi box`.
- **Per box**, kept under the box's `id`: the MAC address (`mac.json`),
  where the volume keys go (`volume.json`), the YouTube mode chosen in
  the remote (`youtube-mode.json`), the YouTube add-on's last failure
  (`youtube-failed.json`) and the shortcut buttons (`shortcuts.json`).
  The first four are `{"boxes": {"<id>": …}}`, the 32 most recently
  changed boxes. Whom a stop went to (`stopped`) names the address: it is
  about the Kodi there. Queued titles (`titles.json`) and the artwork
  cache are shared: a title belongs to a link, an image file to its URL.
- **The move to ids** happens by itself, the first time the daemon reads
  a config with a box that has no `id` (omakodi 0.2's one box, a
  list from before ids, or a box added by hand), under a lock file in the
  state folder (`.boxes.lock`), so two processes never move at once: each such box
  gets a random UUID; its entries in the per-box files, kept under its
  `host` until then (`{"hosts": {"kodi.example.lan": …}}`, or 0.2's
  `{"host": "kodi.example.lan", KEY: …}`), are copied to the id; then
  the config is written with the ids (atomically, mode 600, everything
  else in it as it was, the passwords too; the one-box form stays one
  box, with `id` at the top), then the `host` entries go and `box.json`
  names the box in use by its id. Each file is written atomically (mode
  600). Stopped at any point, nothing is lost: until the config holds
  the ids, a box without one goes by its `host` and reads the old
  entries, and the next start finishes the move. A config that doesn't
  parse, isn't the user's or is readable by others is left alone (the
  user fixes it first). The CLI doesn't move anything: it reads either
  form. Entries of hosts that aren't a saved box stay as they are.
- **Switching**: the daemon reads the box in use whenever `box.json` or
  the config changes. On another box it closes the last box's event port,
  forgets all of its state (what plays, the queue, details, power,
  Kodi's keyboard, a pending volume check) and pushes at once a state with
  `reachable` false, nothing playing and `connecting` true; the new box's
  state follows as soon as it answers (or `not reachable` after one failed
  read: the 45 s grace is for blips, not for another box). The remote's
  open lists and pages for the last box close.
- **Found on your network**: Kodi announces its web server over zeroconf
  as `_xbmc-jsonrpc-h._tcp` (and its TCP JSON-RPC as `_xbmc-jsonrpc._tcp`).
  `discover` runs `avahi-browse --resolve --parsable --terminate` for both
  (10 s at most; the program from PATH), takes the resolved IPv4 lines
  (`\DDD` escapes undone), one per box by the `uuid` in the TXT record
  (else its address), with its name, address and web port, and the live
  port from the second (else 9090); at most 20. The ones whose address or
  hostname and web port match a saved box are left out (no other check
  for duplicates: Add manually can save a second box on a saved address).
  Nothing is sent
  to a found box: no login, no password, until the user adds it and asks.
- **The editor** (see "Remote panel") sends `boxSave` with the box's id
  as `key` (`""` for a new box), and Name, IP address
  or hostname (trimmed; a hostname, IPv4 or IPv6 address as in `host`,
  and one that can be an address, the check of `bad address` in
  "Errors": not `kodi..lan`, nor one with a port), Web port, Live port
  (TCP) (empty: 8080 and 9090), Username, Password and MAC address
  (empty: the one read from Kodi; else as in "Wake-on-LAN"). Save and
  Test connection are refused for an address that can't be one, and Save
  for a MAC address that isn't one: the field shows the config's `mac`
  as written, so one that isn't valid is fixed or emptied there.
  `password` is sent only when it was typed in the field; without it the
  saved one stays, `""` removes it. An empty name is the address. Keys the
  editor doesn't show (`id`, `eventPort`, `wakeOnLan`, a box's
  `youtubeMode`, any other) are kept: a box edited keeps its id, so its
  settings and state stay with it after a change of address. `Boxes.js` checks the fields the same way, so Save
  is only offered for settings the daemon takes (a test runs both over the
  same texts).
- **Saving** writes the config file atomically (a temporary file in its
  folder, mode 600, folder 700, then renamed), JSON with 2-space indents.
  The one-box form becomes the list form on the first save (the
  YouTube mode stays on top, as every box's default); the first box
  creates the file. A file that doesn't parse is never written (`can't
  save`: fix it first). A new box gets a new random id (a UUID) and
  becomes the box in use; the box in use stays in use when edited.
  **Delete** takes the box out and its settings and state with it (its
  entries in every per-box file); a box saved again at that address
  starts with none of them. Deleting the box in use leaves the first;
  deleting the last leaves `{"boxes": []}`. Before either, boxes without
  an id get theirs (the move above).
- **Test connection** (`boxTest`): `Application.GetProperties` `name`,
  `version`, then `XBMC.GetInfoLabels` `System.FriendlyName` and
  `Network.MacAddress`, with the typed login. With the password field
  untouched, the saved password of the box being edited (`key`, its id)
  is used, whatever its address is now (as on a phone remote); a new or
  found box gets none. The answer is `✓ Kodi 21.3` (Kodi's name
  and version), else the error as the phone remote's box screen says it
  (see "Messages"), naming the box by the editor's Name, else its
  address: `Wrong username or password for <box>`, `Can't reach <box>`
  (also a name that doesn't resolve), `<box> answered HTTP <code>`,
  `Unexpected reply from <box>`, `Bad address for <box>`; the others as
  they are. Kodi's name and MAC address
  fill the editor's Name and MAC address when they are empty.
- The password goes from the editor to the daemon in the `boxSave` and
  `boxTest` lines only; it is never in the state, a result, the shell's
  logs, the daemon's output or argv.

## Shell surfaces

### Bar widget

- Hidden while Kodi is not reachable (away from home).
- A Kodi icon while reachable, with a paused mark when paused. The title of
  what plays is in the tooltip; the bar shows it too (elided) when
  `maxTitleLength` is set.
- Click: toggle the remote. Tooltip: title and time, or the error; with
  several boxes, the name of the box in use (its `name`, else its `host`;
  the state's `boxes.current` is its id) first, unless the error's message
  names it already.
- The error reads as the remote's top bar says it (see "Messages"): the
  message in the phone remote's words (`Wrong username or password for
  <box>`, `<box> answered HTTP <code>`, `Unexpected reply from <box>`)
  with the fix on the line under it, nothing in front of it; an error
  with no message of its own (`kodi error: …`) as it is. `Can't reach
  <box>` never shows there: the widget is hidden while Kodi doesn't
  answer.
- `maxTitleLength` (bar widget setting in `shell.json`, default 0 = icon
  only): show the title beside the icon, cut to that many characters. Off by
  default because the bar lets sections overlap and a title easily runs into
  the clock. On a vertical bar, always the icon only, dimmed while paused.
- A Kodi error with Kodi answering (wrong password) shows the icon in the
  urgent colour with the error in the tooltip.

### Remote panel

Opened by the keybinding (`omarchy-shell io.github.frestina.omakodi toggleRemote`)
or the bar widget. Keyboard-first; buttons for the same actions for the mouse.

| Key | Action | Key | Action |
| --- | --- | --- | --- |
| Arrows | `up` `down` `left` `right` | Space | `playpause` |
| Enter | `select` | `+` `-` `m` | `volup` `voldown` `mute` (Kodi's own volume) |
| Backspace | `back` | `c` `i` `o` | `context` `info` `osd` |
| Esc | close the remote | `h` | `home` |
| `p` / `q` | play / queue the clipboard | `x` | `stop` |
| `f` | `fullscreen` | `.` `,` | `next` `previous` |
| `<` / `>` (Shift `<`) | `rewind` `fastforward` | `u` | the Queue dialog (on the now-playing page) |
| `d` | the Details dialog (on the now-playing page) | | |
| `a` | show or hide the audio tracks | `I` (Shift `i`) | `playerinfo` |
| `n` | the now-playing page, or back | `P` (Shift `p`) | the power menu |
| `w` | `wake` (Wake up), unless `wakeOnLan` is false | `s` | `soundbaron` |
| `9` `0` | soundbar down, up (`soundbardown` `soundbarup`) | `S` (Shift `s`) | the settings |
| `1`–`5` | the shortcut buttons, from the left | `e` then `1`–`5` | change that button |
| `b` | the Kodi boxes (Manage Kodi boxes) | `M` (Shift `m`) | the ☰ menu |
| `k` | Type text (the keyboard key) | | |
| Tab / Shift+Tab, Enter | in the Details dialog: the plot's next / previous link, open it | | |

- Layout, top to bottom, keys grouped by what they do:
  1. **Top bar**, as on a phone remote: the ☰ menu button; the box in
     use's name (its `name`, which is its `host` when it has none; "No
     Kodi box yet" without one), and under it the status: **Connected**
     (the theme's green) while Kodi answers, **Offline** (the urgent
     colour) while it doesn't, or answers with an error (a wrong
     password), **Connecting…** (dimmed) until the daemon's first state
     and just after a switch. Under Offline: "Kodi is off" after a shut
     down, "Kodi is restarting…" after a reboot, else Kodi's error in the
     phone remote's words (at most 2 lines) and under it its fix (see
     "Messages") and, when Kodi can't be reached, "Is Kodi on…" (both
     always whole); the daemon's own trouble ("keeps stopping") likewise,
     without the fix. Then the power button and the close button. A
     click on the name opens the menu too.
  2. **Shortcut strip:** the five buttons (see "Shortcut buttons"), 40 px
     keys in a row like the others, so the remote is as tall as with the
     two link buttons it replaces.
  3. **Volume:** `voldown`, `mute`, `volup` (Kodi's own volume); under
     them a slim "Soundbar" row of small keys `soundbardown`,
     `soundbarup` (one step per press, even held: see below), hidden
     once `volumeKeys` is `"kodi"` (they would only repeat the keys
     above).
  4. **Actions**, in a phone remote's order: the audio tracks,
     `fullscreen`, `info`, the keyboard key (Type text) and `playerinfo`.
     Home is on the shortcut strip; the context menu is a long press of
     OK (or a right click on it, or `c`).
  5. **D-pad**, 3×3 keys of 56 px: `up`; `left`, `select` (OK), `right`;
     `back`, `down`, `osd`. The arrows in the theme's accent colour. OK
     selects when let go; held 0.5 s it sends `context` instead, as a
     right click on it does.
  6. **Now playing**, only while something plays, as a phone remote's
     bar: a thin line for how far it is, the thumbnail (a square, the art
     cropped to it; an empty square without art), the title and the
     subtitle, then `stop`, play/pause and `next`, in that order; no time.
     A click on it, or `n`, opens the now-playing page (below).
  7. Over them, while open: the audio track list, a drop-down from the
     audio key over the keys below it (below).
- **The short message**, as a phone remote's: results, a play's
  progress and the remote's own notes ("Nothing to send") show in
  a small box over the bottom of the remote, centred, in the theme's
  notification colours, then fade after 3 s; a new one takes its place.
  An error (urgent border and text) stays until the next action (a key
  or button that sends something, a click on it) or until the remote
  closes. "Change which button?" (after `e`) stays until the next key.
  Answers with a place of their own aren't repeated there: Test
  connection's, the picker's, the network search's and the editor's
  Save and Delete. It is only shown or hidden (opacity), never a layer
  or an effect. The remote opens without one.
- The keys are filled, in the theme's corner radius. As on the phone
  remote they look and work the same while the top bar says Offline: no
  row is dimmed (the strip, the volume keys, the Soundbar row, the action
  row, the D-pad, now playing's keys). A key that needs Kodi, pressed while
  Kodi doesn't answer, sends nothing and says Kodi's error as the short
  message (an error, until the next key): the top bar's message alone
  (`Can't reach <box>`, `Bad address for <box>`, the daemon's own
  trouble), or `Can't reach <box>` when there is none (Kodi is off or
  restarting); a held key says it once. The keys that don't need Kodi work
  as always: Wake up and Turn on soundbar (also `w`, `s`), the power menu
  (its Kodi items go to the daemon, which answers with the error), the ☰
  menu, Settings, Kodi boxes, changing a strip button (`e`, a right click)
  and opening Send a link (its Play and Queue then say the error). While
  Kodi answers with an error (a wrong password) the keys go to Kodi, which
  answers each with it; while Connecting… they go too, and the daemon
  answers.
- While something with art plays, the art fills the remote behind
  everything, blurred and darkened (`MultiEffect`; the compositor doesn't
  blur a plugin's surface), so the text keeps its contrast. The
  now-playing page and its dialogs are opaque over it.
- **The now-playing page** (a click on the bar, or `n`) covers the remote
  like Settings, as a phone remote's now-playing screen:
  - a top bar: a close arrow (Esc), the title and the subtitle, and the
    **Details** and **Queue** buttons (Queue always, also when what plays
    isn't from the queue);
  - the artwork, as large as the room left, cropped, fading into the page
    at the bottom; a film icon without art;
  - the seek bar (the accent colour): click or drag to jump (`seek` on
    release; the wheel jumps 10 s a notch); disabled when the length is
    unknown (live streams). Under it the time played (the place being
    dragged to, in the accent colour, while dragging), in the middle
    "Paused" or "Speed: 2x" (Kodi's speed, "Speed: -4x" rewinding; nothing
    at normal speed), and on the right the length and when it ends at
    normal speed ("47:20 · ends 21:40", local 24 h clock). With hours
    whenever the length is an hour or more ("0:05:12"). Between the
    daemon's reads the position counts on locally at the play speed, so
    the bar moves each second;
  - **previous, rewind, play/pause (large, round), fast-forward, next**.
    Play/pause shows pause only while it plays at normal speed.
  - Keys there: Space, `<` `>`, `.` `,`, the volume keys (`+` `-` `m`),
    `d`, `u`; Esc or `n` close a dialog, then the page. The other
    remote keys (arrows, Enter …) do nothing there: the page has no D-pad.
  - It closes 2.5 s after playback stops (showing the last item until
    then; something new playing keeps it open), when the remote closes,
    and when Kodi's on-screen keyboard opens (its dialog is over the
    remote).
- **Queue** (the page's button, or `u`, which opens the page first) is a
  dialog over the page, as on a phone remote: the title "Queue", then
  "Loading…" until the daemon answers a `refresh` sent when it opens (at
  most 4 s), "The queue is empty" without entries (also while what plays
  isn't from the queue), or the entries ("3. Title", the subtitle under
  it; 7 rows, scrolls), the playing one in the accent colour and bold and
  selected first; a **Close** button. Up/Down choose, Enter or a click
  plays it (`goto`) and closes the dialog; kept from omakodi: Delete or
  its × takes it out (`remove`; not the playing one). Esc, `u`, Close or
  a click beside it close it.
- **Details** (the page's button, or `d`, which opens the page first) is a
  dialog over the page, as a phone remote's details (see "Details"): the
  title, large, and the subtitle under it; **Overview** and the whole
  plot; the badges, outlined and bold, centred; **Info**, a row per field
  with its icon in the accent colour (channel: a person in a circle,
  genre: shapes, show: a TV, date: a calendar, studio: a building, rating:
  a star, age: a shield, runtime: a clock, director: a camera, writer: a
  pencil, country: a globe) and a thin line under its text; **Cast**, a
  row of cards (photo, a person icon without one, the name and the role
  over a dark fade at the bottom) that scrolls sideways. Fields Kodi
  doesn't have are left out; without any it says Kodi has no details. All
  of it scrolls (the wheel; Up/Down, PgUp/PgDn, Home/End), the cast also
  with Left/Right; **Close** stays at the bottom. It opens at the top, and
  goes back there for a new item. Esc, `d`, Close or a click beside it
  close it. Only one of Queue and Details is open at a time.
  The plot's web links are underlined in the accent colour (see "Details");
  over one the pointer is a hand. A click on one opens it in the browser,
  as a tap does on the phone, and the remote closes so the browser has the
  keyboard. Tab marks the next link (Shift+Tab the previous one, round the
  end; the marked one in the card's colour on the accent) and scrolls it
  into view; Enter opens the marked one. Nothing is marked when the dialog
  opens or a new item comes.
- The audio tracks: with one or more, as on a phone remote, the audio
  key's tooltip names the playing one (in the words of "Audio tracks",
  then "2/3", or "1/1"), and it or `a` opens the list of tracks (5 rows,
  then it scrolls; one row for a single track), each in those words, the
  playing one in the accent colour and bold, and selected first (the
  selected row shaded). While it is open, Up/Down choose, Enter plays that
  track (`audio`) and closes the list, `a` or Esc close it; the other keys
  work as usual. A click plays a track; a click beside the list (the audio
  key's included) only closes it, as a tap beside a phone's menu does.
  Enter or a click on the playing one
  sends nothing and only closes the list (so with one track the list only
  shows it). As on the phone remote the key is never dimmed, with
  or without something playing, nor while Kodi doesn't answer (then it
  says Kodi's error, as the other keys): with nothing playing it or `a` says `Nothing
  is playing` (an error, as Space says it) and its tooltip is its name
  alone; while something plays with no tracks it says `No audio streams to
  choose from`; neither opens the list.
- The track list is a drop-down from the audio key, as a phone remote's
  menu: right under the key, its left edge on the key's, over the D-pad
  and now playing (the remote doesn't grow); as wide as its widest row,
  at least 112 px and at most the remote's width (longer rows are cut
  with "…"); in the remote's colour with a thin border, as the power menu.
  Without room under the key it opens over it. Only the rows, no hint
  line. It is always there and only shown or hidden. On the now-playing
  page, which has no audio key (as the phone's), `a` does nothing.
- **The ☰ menu** (its button, a click on the box's name, or `M`), a
  drawer over the left of the remote like a phone remote's side menu,
  the rest of the remote dimmed: the title "omakodi"; "Kodi boxes" and
  each saved box (a TV icon and its name, the one in use in the accent
  colour), a click or Enter switches to it (`box`) and closes the menu;
  a divider; **Manage Kodi boxes** (the Kodi boxes page, below) and
  **Settings**; at the bottom "Version 0.3.0" (the manifest's). Up/Down
  choose (starting on the box in use), Enter picks, Esc, `M` or a click
  beside it close it. It works while Kodi isn't answering.
- **Settings** (in the menu, or `S`) opens the settings over the remote,
  like a phone remote's Settings: "YouTube links", the four modes with a line
  each on what they do (Smart; YouTube add-on first; SendToKodi only;
  YouTube add-on only), the one in use marked. Up/Down choose, Enter or a
  click saves it at once (`youtubeMode`), `S` or Esc close it; opening it
  closes the other lists and the power menu. In `smart` mode, while
  SendToKodi is used after a failure, a line says until when and a row
  "Try the YouTube add-on again" sends `youtubeRetry`. It works while Kodi
  isn't answering too: the choice is omakodi's.
- **Manage Kodi boxes** (in the menu, or `b`) opens **Kodi boxes**, a
  page over the remote like a phone remote's:
  - **Saved**: each box with a radio mark for the one in use, its name and
    `address:port`, and an edit button. A click or Enter switches to it
    (`box`) and goes back to the remote; the edit button, `e` or Right
    opens its editor.
  - **Found on your network**: "Searching…" until a search finds a box,
    "No new boxes found" when all it finds are saved, or "Can't search:"
    and why; then the found boxes (name, `address:port`, a +). A click or
    Enter opens the editor with its name, address and ports. The page
    searches (`discover`) when it opens and every 15 s while it is open.
  - **Add manually** opens an empty editor (username `kodi`, ports 8080
    and 9090).
  - Up/Down choose, Esc or `b` close it; it works while Kodi isn't
    answering (switching away from a box that is off is the point).
- **The editor** ("Add Kodi box", "Edit <name>"): Name, IP address or
  hostname, Web port and Live port (TCP) side by side, Username,
  Password (dots; "Saved; type to change it" while one is saved and
  untouched), MAC address (to wake it; the one read from Kodi as the
  placeholder), the Kodi setup help (Settings → Services → Control and
  the two settings), what is wrong with the fields, **Test connection**
  with its answer beside it, and **Delete** (a saved box; at once, as on
  a phone remote) and **Save**. Up/Down move between the fields and the
  buttons, Left/Right choose a button, Enter in a field saves, Esc goes
  back to Kodi boxes. Saved or deleted, it goes back there; an error
  stays in the editor. The password field is emptied whenever the editor
  closes.
- The power button (or `P`) opens the power menu, a list under it over
  the remote, in a phone remote's order: **Wake up (Wake-on-LAN)**
  (`wake`; hidden when the config's `wakeOnLan` is false), **Turn on
  soundbar (HDMI-CEC)** (`soundbaron`, like `s`), **Kodi power menu**
  (`powermenu`), a divider, **Reboot** and **Shut down**, these two only
  when Kodi allows them (omakodi's extra). It is always there, also while
  Kodi isn't answering: Wake up is how it comes back; what Kodi can't do
  then, it answers with the error. Up/Down choose, Enter or a click picks
  and closes it, `P`, Esc or a click beside it close it; opening it closes
  the other lists. Wake up, the soundbar and Kodi's power menu go at once.
- Reboot and Shut down ask in a dialog over the remote: "Reboot
  <box>?" (the title's name) with **Cancel** and **Reboot** ("Shut down
  <box>?", **Shut down** the same). The keyboard's cursor starts on
  Cancel; Left/Right (or Tab) move it, Enter picks, Esc or a click
  beside it cancels. Only Enter on Reboot, or a click on it, sends it.
  The dialog closes when Kodi stops allowing it. No key reboots or
  shuts down by itself.
- Opens centred below the bar on the focused monitor, clear of the bar
  (so the bar icon still toggles it), with a close button. It keeps the
  keyboard while open, wherever the mouse is on that monitor; a click outside
  it closes it, like Omarchy's own menus. Clicks on the bar still reach it.
- `p` / `q` read the clipboard as text and send it like `omakodi play` /
  `queue`.
- The shortcut strip: a click or `1`–`5` opens a button (while Kodi
  doesn't answer, it says Kodi's error, above); a right click, holding it 0.5 s, or `e` then its
  number opens the button's page ("Change which button?" shows after `e`;
  any other key cancels). Its tooltip names it and says how to change it.
  The strip's pages cover the remote like Settings and have the keyboard
  until closed:
  - **Send a link** (the Send a link button): a text field ("YouTube, X,
    Rumble, … link"), filled with the clipboard's link when it holds one;
    Paste while it is empty, Clear while it isn't; **Play** and **Queue**,
    enabled once it holds a link (the check `omakodi play` makes), and
    **Cancel**. Enter plays, Shift+Enter queues, Esc cancels.
  - **The button's page**: its icon and name ("(default)" while it is
    one); **Choose from Kodi…**; **Use "Send a link"** (unless it is that
    already); **Change icon**; then "Or type a Kodi path or add-on, e.g.
    plugin://plugin.video.youtube", a field with the typed path, and
    **Reset** (once changed), **Cancel**, **Save** (enabled when the field
    changed and is empty or a path the daemon takes). Up/Down choose a row
    (the field takes typing while chosen), Left/Right a button in the last
    row, Enter picks (in the field: Save), Esc cancels. A pick saves at
    once and closes the page.
  - **Choose from Kodi**: the page's title (and the way there) with a back
    arrow and a close button; "Use this folder" first on a folder; the
    rows, ones that open a page marked ›; "Loading from Kodi…", "No
    folders here" (a folder) or "Nothing here", or "Couldn't load" with
    Kodi's error and a **Try again** row. Up/Down choose, Enter or Right
    opens or picks, Backspace or Left goes back (from the first page to the
    button's page), Esc closes it (back to the button's page). 10 rows
    show; the list scrolls.
  - **Choose icon**: Kodi's icon ("The artwork Kodi has for this"), or
    Automatic ("Kodi has no artwork for this"), on a row of its own, then
    the built-in icons in rows of 8, the one in use filled and the
    keyboard's choice ringed. Arrows move, Enter picks, Esc goes back.
- A held key's repeats are sent only once Kodi has answered the previous
  key, so holding an arrow on a slow Kodi never builds a backlog. During
  plain fullscreen video a held arrow skips once (see "Daemon protocol").
- Held with the mouse, the arrows and Kodi's volume keys (`volup`
  `voldown`) repeat like a real remote's: they send on the press, again
  after 0.4 s, then every 0.11 s, as held keyboard keys' repeats (with
  `repeat: true`, so the same rule applies); moving off the key stops
  it. The other keys send on a click.
- The soundbar keys (`soundbardown` `soundbarup`) and `mute` send once
  per press however long they are held, with the mouse and on the
  keyboard (a held `9`, `0` or `m` sends once; its repeats are dropped),
  so a held soundbar key moves the soundbar one step (the user's choice).
- **Kodi's keyboard**: when Kodi asks for text (`input` is set), a dialog
  opens over the remote, as on a phone remote: Kodi's prompt as its title
  ("Send text to Kodi" when Kodi gives none), a text field with Kodi's
  text (empty for a password, and when the keyboard key found the
  keyboard: see `keyboard` in "Daemon protocol"), dots for a password, a
  **Paste** button beside it (the clipboard in place of the selection,
  line breaks as spaces, at most 300 characters in all), then **Cancel**
  and **Send**. The field has the keyboard. Nothing reaches Kodi while
  typing: **Send** (or Enter) sends the text once and submits it (`text`
  with `done: true`) and closes the dialog; **Cancel** (or Esc, or a
  click beside the dialog) only closes it, and Kodi's keyboard stays on
  the TV. The dialog closes when Kodi's keyboard closes, and its text is
  forgotten whenever it closes. It is over everything else in the
  remote; what was open under it is there again once it closes. Opening
  the remote while Kodi asks for text opens it again.
- The keyboard key (or `k`): while Kodi asks for text, it opens the
  dialog again (after Cancel); else the daemon asks Kodi (`keyboard`) and
  the dialog opens, or the remote says "Kodi isn't asking for text right
  now". The key is marked while Kodi asks for text. A keyboard the key
  found without the event port (`input.recheck`): the key asks Kodi again
  each time, and the dialog opens only when it is still open; once Kodi
  says no, the key is no longer marked and the remote says so.
- Left/Right go through `Util.readingKey(event)` for right-to-left languages.
- Strings in `i18n/en.json` via `Commons.Translations`.

### IPC target `io.github.frestina.omakodi`

| Method | Does |
| --- | --- |
| `toggleRemote()` / `openRemote()` / `closeRemote()` | the panel |
| `play(text)` / `queue(text)` | send a link through the daemon |
| `control(action)` | a remote action |
| `seek(seconds)` | jump in what plays |
| `shortcut(button)` | open shortcut button 1–5 (Send a link is refused) |
| `status()` | JSON of the current state |

- The others answer `ok` once the command is handed to the daemon, or the
  reason it wasn't (`unknown action; …`, `no link found`, `omakodi daemon
  isn't running`, `busy: too many commands waiting`). `no link found` comes
  from `Protocol.js`, which finds a link exactly as `omakodi play` does
  (step 1 of "Sending a link"; a test runs both over the same texts). The
  outcome of a `play` arrives later and shows in the remote and in `status()`
  (`lastResult`).
- `status()`: `{"daemon": "running", "ready": true, "reachable": true,
  "error": "", "playing": {…} | null, "volume": 80 | null, "muted": false,
  "input": {…} | null, "queue": {…} | null, "details": {…} | null,
  "boxes": {"current": …, "list": […]}, "connecting": false, "pending": 0,
  "lastResult": {"id", "cmd", "ok", "text"} | null}`.
- The service runs `/usr/bin/python3 -I <plugin dir>/bin/omakodi daemon`,
  never a `python3` or `omakodi` found on PATH. When the daemon exits it
  starts it again after 1 s, doubling to 60 s, back to 1 s after a run of
  30 s; after three quick exits in a row `error` says the daemon keeps
  stopping. Disabling or reloading the plugin stops it.

### Keybindings

Documented in the README, not installed: `omarchy plugin add` runs no
install hooks, and users choose their own keys. Three bindings, for
`~/.config/hypr/bindings.lua`:

| Key | Binding | Command |
| --- | --- | --- |
| `SUPER SHIFT + K` | Open the remote | `omarchy-shell io.github.frestina.omakodi toggleRemote` |
| `SUPER SHIFT ALT + K` | Play clipboard link | `omakodi play --clipboard --notify` |
| `SUPER SHIFT CTRL + K` | Queue clipboard link | `omakodi queue --clipboard --notify` |

```lua
o.bind("SUPER + SHIFT + K", "Kodi remote", "omarchy-shell io.github.frestina.omakodi toggleRemote")
o.bind("SUPER + SHIFT + ALT + K", "Play link on Kodi", "omakodi play --clipboard --notify")
o.bind("SUPER + SHIFT + CTRL + K", "Queue link on Kodi", "omakodi queue --clipboard --notify")
```

The play and queue bindings' notifications say what the remote says
(see "Messages").

K for Kodi. Omarchy 4's defaults use `SUPER + K` and `SUPER ALT/CTRL + K`
(keybinding cheat sheets) and leave the `SUPER SHIFT + K` family free.
The three share one letter so they are easy to remember and to move
together.

`install.sh` (optional, run from the plugin folder) links `bin/omakodi`
into an existing `~/.local/bin` (on Omarchy's session PATH) and prints the
config template and these bindings. It never creates `~/.local/bin`, writes
the config or edits Hyprland files; it leaves alone a file or a link it
didn't make. `install.sh --uninstall` removes only its own link.
`omakodi init` writes the config template with mode 600 (directory 700)
and refuses to overwrite one.

## Removal

`omarchy plugin remove` leaves `~/.config/omakodi/` (it holds the password;
the README says to delete it), `~/.local/state/omakodi/` (the box in
use, and per box the YouTube health note, the YouTube mode chosen in the
remote, the last stop, the MAC address, where the volume keys go and the
shortcut buttons; queued titles) and
`~/.cache/omakodi/`. Keybindings the user added are theirs to remove. The
`~/.local/bin/omakodi` link from `install.sh` points into the plugin folder,
so it is removed with `install.sh --uninstall` before `omarchy plugin
remove` (or with `rm` after, when it is left broken). `install.sh
--uninstall` then lists what stays, the same folders and keybindings as
the README's "Removal" (all but that link, which it has just removed).

## Testing

- `tests/run`: manifest validation, Python unit tests (`python3 -I -m
  unittest`), `omarchy plugin validate` when available.
- `tests/fakekodi.py`: a fake Kodi with JSON-RPC over HTTP (Basic auth,
  scripted replies) and the TCP event port (scripted notifications). Used by
  the tests and by the demo (`demo/run -- demo/capture`) for the
  marketplace screenshot and the README's animation.
- Fixtures are fictional: `kodi.example.lan`, made-up titles. No real
  addresses, hostnames or account names in the repo, tests or docs.
- Live checks against a real Kodi are recorded in a git-ignored
  `docs/live-checks.local.md`.
