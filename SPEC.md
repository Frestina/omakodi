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

`~/.config/omakodi/config.json`:

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

- `host` is required. Ports default to 8080 and 9090; `eventPort`, Kodi's
  EventServer (see "Power"), to 9777. `username` and
  `password` may be left out when Kodi's web server has no login.
- Optional, for Wake-on-LAN (see "Power"): `mac`, the box's MAC address
  (`aa:bb:cc:dd:ee:ff` or with `-`), which overrides the one the daemon
  read from Kodi; `wakeOnLan: false` turns waking off (no "Wake Kodi" in
  the remote, the MAC isn't read), for a box that can't be woken (a
  Raspberry Pi).
- The file must be owned by the user and not readable by group or others when
  it holds a password. Otherwise `omakodi` refuses it with
  `config readable by others` and the fix (`chmod 600`).
- The password never appears in argv, `shell.json`, the daemon's output,
  error messages or logs. Kodi's own replies can contain secrets (a stream
  URL from a media-server add-on can carry an API key), so the stream `file`
  of the playing item is never emitted.
- Plugin settings that hold no secrets go in the bar widget's `shell.json`
  schema: `maxTitleLength`.
- **The YouTube mode is chosen in the remote** (its Settings, below), per
  box, like a phone remote's settings: kept in
  `~/.local/state/omakodi/youtube-mode.json` (`{"host":
  "kodi.example.lan", "mode": "youtube-first"}`, mode 600) for the config's
  `host`, and read by every `omakodi` process (the play keybindings'
  included) for each play or queue. Until one is chosen for the box, the
  config file's `youtubeMode` (default `smart`). `omakodi config` shows
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

Every failure has one wording and one exit code. The CLI prints the wording
on stderr; the daemon reports it as `error`.

| Error | Meaning | Exit |
| --- | --- | --- |
| `not configured` | No config file | 3 |
| `bad config` | Not JSON, or `host` missing, or a wrong type | 3 |
| `config readable by others` | Holds a password and mode allows group/other | 3 |
| `not reachable` | Connect failed or timed out (away from home?) | 4 |
| `wrong username or password` | HTTP 401 | 5 |
| `http <code>` | Any other non-200 | 1 |
| `bad response` | Not JSON-RPC | 1 |
| `kodi error: <message>` | JSON-RPC `error` member | 1 |
| `nothing playing` | A player command with no active player | 1 |
| `no link found` | `play`/`queue` text had no http(s) URL | 2 |
| `SendToKodi isn't installed` | Needed add-on missing or disabled | 1 |
| `SendToKodi couldn't play it` | SendToKodi gave up on the link (see "Sending a link") | 1 |
| `can't reach Kodi's EventServer` | The EventServer packet couldn't be sent (the name doesn't resolve, no network) | 4 |
| `can't wake Kodi` | No MAC address known, `wakeOnLan` is false, or the packet couldn't be sent | 1 |
| `that button sends a link` | A shortcut button that is Send a link was asked to open on Kodi | 2 |
| `not a Kodi path or add-on` | A typed shortcut path that is neither (see "Shortcut buttons") | 2 |
| usage errors | Bad arguments | 2 |

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
     fallback, no `smart` record, the message `Stopped`.

   A `stop` sent through omakodi (the remote's `x`, `omakodi control
   stop`, IPC) writes the time to `~/.local/state/omakodi/stopped` before
   it goes to Kodi, because the watch may run in another process (the
   keybinding's `omakodi play`). A watch that sees a stop noted after it
   opened the item (on a `Player.OnStop`, and at each poll) decides
   "stopped". A stop from Kodi's own remote can't be told apart from a
   failure.

   On failure: record the time for `smart` mode, say "YouTube add-on couldn't
   play it, trying SendToKodi", and open the SendToKodi path. On success
   clear the record. In the queue the SendToKodi item takes the failed item's
   place (`Playlist.Remove`; right after it if Kodi won't remove it).
6. **SendToKodi is watched too**, whenever `play` opens a SendToKodi item
   (the route, or the fallback above). When yt-dlp can't play a link
   (removed, login wall), Kodi sends no event at all; only its busy
   dialog tells (checked live): Kodi's `busydialog` (or
   `busydialognocancel`, `progressdialog`, `extendedprogressdialog`) shows
   while SendToKodi works, then either the new item plays or the dialogs
   close, a notification shows on the TV, and nothing plays. Listening on
   the event port before opening, with `progress` "SendToKodi is opening
   it…", polling `XBMC.GetInfoBooleans` and the player every 0.5 s for up
   to 60 s:
   - **playing:** the new item is in the player (a different `file|label`
     from before, or at the queue slot), or `Player.OnAVStart` after its
     `Player.OnPlay`.
   - **failed:** `Player.OnStop` of the new item before its picture came
     up; or the busy dialog was seen, then has been gone for 3 s with no
     new item (the dialog can blink off for half a second between steps).
   - **undecided** after 60 s (still busy, or never busy).
   - **stopped:** as in step 5: `Stopped`, no error.

   Messages: playing `Playing on Kodi` (plus the route note); failed the
   error `SendToKodi couldn't play it: Kodi shows why on the TV`;
   undecided `Sent to Kodi; SendToKodi is still opening it`.
7. **Queue**: if nothing plays (`Player.GetActivePlayers` empty), play
   instead. Otherwise `Playlist.Add` to the video playlist (id 1) and report
   the queue length. No fallback, since it plays later.

Messages: `Playing on Kodi…` (`Playing on Kodi` once it is known to play),
`Queued on Kodi (3 in queue)`, plus the route note when the usual add-on
wasn't used.

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
| `volup` `voldown` | Kodi's own volume 5% up / down: `Application.GetProperties` `volume`, then `Application.SetVolume` with the number (0 to 100); see "Volume" |
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
5, from the left) of the config's box on Kodi (see "Shortcut buttons");
Send a link is refused (`that button sends a link`, exit 2).

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
```

Out:

```json
{"type": "state", "reachable": true, "error": "", "playing": {"title": "…", "subtitle": "…", "kind": "video", "paused": false, "speed": 1, "positionSec": 393, "durationSec": 3009, "art": ""}, "volume": 80, "muted": false, "queue": null, "details": null, "audio": null, "power": null, "wake": false, "volumeKeys": "unknown", "youtube": {"mode": "smart", "from": "config", "avoidUntil": 0, "box": "kodi.example.lan"}, "shortcuts": {"box": "kodi.example.lan", "buttons": [{"label": "Home", "sendLink": false, "icon": "", "art": "", "auto": "home", "custom": false, "typed": ""}, …]}, "input": null}
{"type": "picker", "seq": 6, "title": "YouTube", "crumb": "YouTube", "folder": true, "depth": 3, "status": "ready", "error": "", "items": [{"label": "Trending", "detail": "", "browse": true}]}
{"type": "progress", "id": 8, "message": "The YouTube add-on couldn't play it, trying SendToKodi…"}
{"type": "result", "id": 8, "ok": true, "message": "Playing on Kodi…"}
{"type": "result", "id": 7, "ok": false, "error": "not reachable: …"}
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
  (`box`, the config's `host`). It is there whatever Kodi
  answers: the choice doesn't need Kodi. `youtubeMode` saves a mode for the
  box; `youtubeRetry` forgets the add-on's failure, so the next YouTube
  link tries it again. Both run in line with the remote actions.
- `shortcuts` is the config's box's five shortcut buttons (see "Shortcut
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
  `wakeOnLan` isn't false. `wake` runs in line with the remote actions.
- `seek` runs in line with the remote actions; `seconds` is a whole number
  from 0 to 7 days.
- `input` is set while Kodi's on-screen keyboard is open (event
  `Input.OnInputRequested`): `{"type": "keyboard", "title": "Search",
  "value": ""}`; `value` is always `""` for the password types. It goes back
  to `null` on `Input.OnInputFinished` or when the event port reconnects.
  `text` sends `Input.SendText` (`done: true` submits it).
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
  restart of the shell.
- A line that isn't a valid command is answered with
  `{"type":"result","id":<id or null>,"ok":false,"error":"bad request: …"}`;
  lines over 16 KiB are dropped the same way. The daemon never exits on bad
  input; it exits when stdin closes.
- All strings are bounded (titles, messages and errors 300 chars) and emitted
  as data; the QML shows them as plain text.

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
  the type's extension. The 30 most recently used are kept. An image already
  there is used without asking Kodi again.
- The state carries only that local path (`playing.art`), once the file is
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

- The daemon reads them on a new item only, not on every poll: when the
  playing item's type, library id, label, title, show, season, episode,
  artist, album or art differ from the last read. It asks `Player.GetItem`
  for `plot`, `plotoutline`, `genre`, `year`, `premiered`, `firstaired`,
  `studio`, `rating`, `cast` and `streamdetails`, and `Player.GetProperties`
  for `currentvideostream` and `currentaudiostream`. When the playing streams
  weren't known yet (an item that has only just started), it reads them once
  more after the next `Player.OnAVStart`.
- The state carries `"details": {"plot": "…", "genres": ["Drama"], "year":
  2019, "studio": "…", "rating": "7.8", "cast": ["…"], "badges": ["1080p",
  "HDR10", "5.1", "TrueHD"]}`. Empty fields are left out; `null` while
  nothing plays or when Kodi knows none of it (add-on items often have
  little more than a plot).
- Bounds: `plot` (else `plotoutline`) 3000 characters, cut with "…";
  `genres` 5 of 40; `studio` the first two, 120; `cast` the first 10 names
  of 60; `rating` above 0 up to 10, one decimal; `year` 1800–2200, else the
  year of `premiered` or `firstaired`; `badges` at most 4 of 20.
- Plain text: Kodi's formatting tags (`[B]`, `[I]`, `[LIGHT]`, `[COLOR …]`,
  `[UPPERCASE]`, `[LOWERCASE]`, `[CAPITALIZE]`, `[TABS]` and their closing
  tags) are taken out and `[CR]` becomes a line break; control characters
  go. The plot keeps its line breaks (no more than one empty line in a row);
  every other field is one line.
- Badges, in this order: the resolution from the playing video stream, else
  the library's `streamdetails` (Kodi's own steps: SD, 720p, 1080p, 4K, 8K);
  the HDR type from `streamdetails` (HDR10, HDR10+, Dolby Vision, HLG, else
  HDR); the audio channels (Mono, Stereo, 5.1, 7.1, else `N ch`) and codec
  (AAC, AC3, E-AC3, DTS, DTS-HD MA, DTS:X, TrueHD, Atmos variants, FLAC, Opus,
  MP3, PCM …; an unknown codec in capitals, letters and digits only) from the
  playing audio stream, else `streamdetails`.
- An answer that can't be used (an error, over 1 MB) gives no details; only
  a lost connection or a wrong password fails the read.

## Audio tracks

- Read on every poll in the same `Player.GetProperties` call as the time
  (`audiostreams`, `currentaudiostream`), so a track switched on the TV
  shows too.
- `"audio": {"current": 1, "tracks": [{"index": 0, "name": "…",
  "language": "eng", "codec": "AC3", "channels": "5.1"}]}`; `null` while
  nothing plays or Kodi lists no tracks. `current` is the `index` of the
  playing track, or -1 when that isn't one of the listed ones.
- Bounds: at most 32 tracks, `index` 0–999 (others are left out); `name`
  100 characters of plain text on one line (as in "Details"); `codec` and
  `channels` the same words as the details badges, or `""`.
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

- `volup`, `voldown`, `mute` (`+` `-` `m`) act on Kodi's own volume: 5% a
  step (from the level Kodi reports, kept within 0 to 100) and mute on or
  off. The remote's "Volume 80%" is that level.
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
  (`{"host": "kodi.example.lan", "keys": "tv"}`, mode 600), so the remote
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
- UDP has no answer: the result says `Asked Kodi to turn on the soundbar`
  whether or not anything listens. It only fails when the packet can't be
  sent (`can't reach Kodi's EventServer`).

### Wake-on-LAN

- Each time Kodi answers after the daemon starts, after it was off or
  restarting, or after the config changes, the daemon reads the box's MAC
  address (`XBMC.GetInfoLabels` `Network.MacAddress`). Kodi says `Busy`
  while it looks it up, so a reply that isn't a MAC address is asked again
  at the next read, up to 5 times. A valid one is kept in
  `~/.local/state/omakodi/mac.json` (`{"host": "kodi.example.lan", "mac":
  "aa:bb:cc:dd:ee:ff"}`, mode 600, written only when it changes), for the
  config's `host` only: another `host` reads it again.
- A MAC address is six hex pairs split by `:` or `-` (one kind), kept in
  lower case with `:`. All zeros and multicast addresses (lowest bit of the
  first byte set, so also `ff:ff:ff:ff:ff:ff`) aren't a box's and are
  refused.
- The config's `mac` wins over the saved one; `wakeOnLan: false` turns all
  of it off.
- Waking sends the magic packet (6 bytes `ff`, then the MAC 16 times; 102
  bytes) three times over UDP to the broadcast address `255.255.255.255`
  port 9. It answers `Wake-up sent; Kodi takes a minute to start`. Kodi
  can't say whether the box got it: the state shows it once Kodi answers.
- The box must have Wake-on-LAN on and a wired connection (README).

## Shortcut buttons

A strip of five buttons under the remote's header, as on a phone remote:
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
  the config's `host`: `{"boxes": {"kodi.example.lan": [null, {…}, null,
  null, null]}}`, `null` for a button at its default (a default with only
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

## Shell surfaces

### Bar widget

- Hidden while Kodi is not reachable (away from home).
- A Kodi icon while reachable, with a paused mark when paused. The title of
  what plays is in the tooltip; the bar shows it too (elided) when
  `maxTitleLength` is set.
- Click: toggle the remote. Tooltip: title and time, or the error.
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
| `<` / `>` (Shift `<`) | `rewind` `fastforward` | `u` | show or hide the queue |
| `d` | show or hide the details | `D` (Shift `d`) | the whole plot, or a few lines again |
| `a` | show or hide the audio tracks | `I` (Shift `i`) | `playerinfo` |
| `n` | show more or less of what plays | `P` (Shift `p`) | the power menu |
| `w` | wake Kodi, while it isn't answering | `s` | `soundbaron` |
| `9` `0` | soundbar down, up (`soundbardown` `soundbarup`) | `S` (Shift `s`) | the settings |
| `1`–`5` | the shortcut buttons, from the left | `e` then `1`–`5` | change that button |

- Layout, top to bottom, keys grouped by what they do:
  1. **Header:** "Kodi remote", Kodi's own volume ("Volume 80%", "Muted") or why
     Kodi can't be reached, with the fix ("Kodi is off" after a shut down,
     "Kodi is restarting…" after a reboot; Kodi's error at most 2 lines,
     the fix always whole), the power button and the close button. The power menu opens under it. While Kodi isn't answering (or
     is off) and `wake` is true, a "Wake Kodi" button under it (or `w`)
     sends `wake`; it asks nothing first, since waking can't harm.
  2. Kodi's on-screen keyboard field, while it is open (below).
  3. **Shortcut strip:** the five buttons (see "Shortcut buttons"), 40 px
     keys in a row like the others, so the remote is as tall as with the
     two link buttons it replaces.
  4. **Volume:** `voldown`, `mute`, `volup` (Kodi's own volume); under
     them a slim "Soundbar" row of small keys `soundbardown`,
     `soundbarup`, hidden once `volumeKeys` is `"kodi"`
     (they would only repeat the keys above).
  5. **Actions:** the audio tracks, `fullscreen`, `info`, `home`,
     `context`, `playerinfo`.
  6. **D-pad**, 3×3 keys of 56 px: `up`; `left`, `select` (OK), `right`;
     `back`, `down`, `osd`. The arrows in the theme's accent colour. A
     right click on OK sends `context`.
  7. **Now playing**, only while something plays: a thin line for how far
     it is, the art (64 px tall, kept in proportion; none without art), the
     title, the subtitle and elapsed / total, and play/pause, `next` and
     `stop`. A click on it, or `n`, shows more under it: rewind, a seek bar
     and fast-forward; elapsed / total, "ends HH:MM" (local 24 h clock, at
     normal speed) and the speed when it isn't normal; then `previous`,
     Details and Queue (N). `n` again shows less and closes any list.
  8. The last result, progress or error.
- The keys are filled, in the theme's corner radius. Not reachable: the
  keys are disabled.
- While something with art plays, the art fills the remote behind
  everything, blurred and darkened (`MultiEffect`; the compositor doesn't
  blur a plugin's surface), so the text keeps its contrast.
- The seek bar: click or drag to jump (`seek` on release; the wheel jumps
  10 s a notch); no bar when the length is unknown (live streams). Between
  the daemon's reads the position counts on locally at the play speed, so
  the bar moves each second.
- The queue: while the video queue plays, "Queue (N)" (or `u`) opens its
  list (5 rows, scrolls), the playing entry marked ▶ and selected first.
  While it is open, Up/Down choose an entry, Enter plays it (`goto`),
  Delete takes it out (`remove`; not the playing one), `u` or Esc close
  the list and give the arrows back to Kodi; the other keys work as usual.
  A click plays an entry; its × removes it.
- The details: "Details" (or `d`) opens the details card: year · genres ·
  studio · ★ rating, the badges, the plot cut to 4 lines (`D`, a click on
  it or its More button shows all of it, scrolling with the wheel past
  about 12 lines), and the cast on up to 2 lines. Fields Kodi doesn't have
  are left out; with none at all the card says Kodi has no details. A new
  item shows its plot cut again.
- The audio tracks: with two or more, the audio key's tooltip names the
  playing one (language · name · codec and channels, with no part twice
  and the sound only when the name doesn't already say it; "Track N" when
  there is nothing else; then "2/3"), and it or `a` opens the list of
  tracks (5 rows), the playing one marked ▶ and selected first. While it is
  open, Up/Down choose, Enter plays that track (`audio`) and closes the
  list, `a` or Esc close it; the other keys work as usual. A click plays a
  track. With one track or none the key is dimmed and `a` says so.
- The queue list, the details card and the track list open under now
  playing (showing more of it); only one of them is open at a time, so the
  remote fits on a screen 800 px tall.
- The settings button (or `S`) opens the settings under the header, like
  a phone remote's Settings: "YouTube links", the four modes with a line
  each on what they do (Smart; YouTube add-on first; SendToKodi only;
  YouTube add-on only), the one in use marked. Up/Down choose, Enter or a
  click saves it at once (`youtubeMode`), `S` or Esc close it; opening it
  closes the other lists and the power menu. In `smart` mode, while
  SendToKodi is used after a failure, a line says until when and a row
  "Try the YouTube add-on again" sends `youtubeRetry`. It works while Kodi
  isn't answering too: the choice is omakodi's.
- The power button (or `P`) opens the power menu under the header: Kodi's
  power menu (`powermenu`), Turn on the soundbar (`soundbaron`, at once,
  like `s`),
  Reboot and Shut down, the last two only when Kodi allows them. Up/Down choose, Enter or a click picks, `P` or Esc close it;
  opening it closes the other lists. Reboot and Shut down ask again: the
  first pick turns the row into "Press again to reboot" (or shut down) for
  5 seconds, and only a second Enter or click on that row within them
  sends it. Moving to another row, closing the menu or the 5 seconds
  passing cancels it. No other key reboots or shuts down. The button is
  disabled while Kodi isn't reachable.
- Opens centred below the bar on the focused monitor, clear of the bar
  (so the bar icon still toggles it), with a close button. It keeps the
  keyboard while open, wherever the mouse is on that monitor; a click outside
  it closes it, like Omarchy's own menus. Clicks on the bar still reach it.
- `p` / `q` read the clipboard as text and send it like `omakodi play` /
  `queue`.
- The shortcut strip: a click or `1`–`5` opens a button (disabled while
  Kodi isn't reachable); a right click, holding it 0.5 s, or `e` then its
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
- While Kodi's on-screen keyboard is open, the remote shows a text field with
  Kodi's title and text, and it has the keyboard: what you type shows on the
  TV, Enter submits it, Esc closes Kodi's keyboard. Password input shows dots.
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
  "pending": 0, "lastResult": {"id", "cmd", "ok", "text"} | null}`.
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
the README says to delete it), `~/.local/state/omakodi/` (the YouTube
health note, the YouTube mode chosen in the remote, the time of the last stop, queued titles, the box's MAC address, where its volume
keys go and its shortcut buttons) and
`~/.cache/omakodi/`. Keybindings the user added are theirs to remove. The
`~/.local/bin/omakodi` link from `install.sh` points into the plugin folder,
so it is removed with `install.sh --uninstall` before `omarchy plugin
remove` (or with `rm` after, when it is left broken).

## Testing

- `tests/run`: manifest validation, Python unit tests (`python3 -I -m
  unittest`), `omarchy plugin validate` when available.
- `tests/fakekodi.py`: a fake Kodi with JSON-RPC over HTTP (Basic auth,
  scripted replies) and the TCP event port (scripted notifications). Used by
  the tests and by the demo for the marketplace screenshot.
- Fixtures are fictional: `kodi.example.lan`, made-up titles. No real
  addresses, hostnames or account names in the repo, tests or docs.
- Live checks against a real Kodi are recorded in a git-ignored
  `docs/live-checks.local.md`.
