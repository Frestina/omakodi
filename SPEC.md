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
| Cache | `~/.cache/omakodi/` (artwork, v2) |
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

- `host` is required. Ports default to 8080 and 9090. `username` and
  `password` may be left out when Kodi's web server has no login.
- The file must be owned by the user and not readable by group or others when
  it holds a password. Otherwise `omakodi` refuses it with
  `config readable by others` and the fix (`chmod 600`).
- The password never appears in argv, `shell.json`, the daemon's output,
  error messages or logs. Kodi's own replies can contain secrets (a stream
  URL from a media-server add-on can carry an API key), so the stream `file`
  of the playing item is never emitted.
- Plugin settings that hold no secrets (none in v1) go in the bar widget's
  `shell.json` schema.

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
3. **Route**, by `youtubeMode`:

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
5. **Play** (`Player.Open`). With the YouTube add-on and a fallback, watch for
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
     a different `file|label` from before, or the same one restarted.

   On failure: record the time for `smart` mode, say "YouTube add-on couldn't
   play it, trying SendToKodi", and open the SendToKodi path. On success
   clear the record. SendToKodi itself is not watched: it can take 20 s or
   more and shows its own errors on the TV.
6. **Queue**: if nothing plays (`Player.GetActivePlayers` empty), play
   instead. Otherwise `Playlist.Add` to the video playlist (id 1) and report
   the queue length. No fallback, since it plays later.

Messages: `Playing on Kodi…`, `Queued on Kodi (3 in queue)`, plus the route
note when the usual add-on wasn't used.

## Remote commands

`omakodi control <action>`:

| Action | Kodi call |
| --- | --- |
| `up` `down` `left` `right` | `Input.Up` … ; during plain fullscreen video: `Input.ExecuteAction` `chapterorbigstepforward` / `chapterorbigstepback` / `stepback` / `stepforward` |
| `select` | `Input.Select`; during fullscreen video: `Input.ShowOSD` |
| `back` `info` `context` `osd` | `Input.Back`, `Input.Info`, `Input.ContextMenu`, `Input.ShowOSD` |
| `home` | `GUI.ActivateWindow` `home` |
| `playpause` `stop` | `Player.PlayPause`, `Player.Stop` on the active player |
| `volup` `voldown` | `Application.SetVolume` `increment` / `decrement` |
| `mute` | `Application.SetMute` `toggle` |
| `fullscreen` | `GUI.SetFullscreen` `toggle` |

"Plain fullscreen video" = `Window.IsActive(fullscreenvideo)` and no modal
dialog and no OSD (`XBMC.GetInfoBooleans`), cached briefly so arrow keys stay
fast. `omakodi status` prints the now-playing JSON (below) once.

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
```

Out:

```json
{"type": "state", "reachable": true, "error": "", "playing": {"title": "…", "subtitle": "…", "kind": "video", "paused": false, "positionSec": 393, "durationSec": 3009}, "volume": 80, "muted": false, "input": null}
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
  `stop`, volume, `mute`, `play`, `queue`) it is read again at once.
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
| Enter | `select` | `+` `-` `m` | `volup` `voldown` `mute` |
| Backspace | `back` | `c` `i` `o` | `context` `info` `osd` |
| Esc | close the remote | `h` | `home` |
| `p` / `q` | play / queue the clipboard | `x` | `stop` |
| `f` | `fullscreen` | | |

- Shows the now-playing line (title, time, paused) and the last result or
  error. Not reachable: says so with the fix, keys disabled.
- Opens centred below the bar on the focused monitor, clear of the bar
  (so the bar icon still toggles it), with a close button. It keeps the
  keyboard while open, wherever the mouse is on that monitor; a click outside
  it closes it, like Omarchy's own menus. Clicks on the bar still reach it.
- `p` / `q` and the Play link / Queue link buttons read the clipboard as
  text and send it like `omakodi play` / `queue`.
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
  "input": {…} | null, "pending": 0, "lastResult": {"id", "cmd", "ok",
  "text"} | null}`.
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
the README says to delete it), `~/.local/state/omakodi/` and
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
