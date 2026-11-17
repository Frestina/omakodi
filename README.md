# omakodi

[![Built for Omarchy: Plugin](https://raw.githubusercontent.com/tcballard/omarchy-badges/75975e5b5bf75e7ede3764bcd2950046f7abfe2c/badges/v1/omarchy-plugin.svg)](https://github.com/tcballard/omarchy-badges)

A keyboard remote for Kodi on Omarchy. Send a link from the clipboard to play
or queue it, drive Kodi's menus from the keyboard, and see what is playing in
the bar, without picking up a phone.

Kinds: service, bar-widget, panel

## What it does

- **Play or queue a link.** Copy a video link, press a key, and Kodi plays
  it, or adds it to its queue. YouTube links go to the YouTube add-on, with
  SendToKodi as the fallback; everything else goes to SendToKodi. A
  notification says what happened.
- **The remote.** A small panel below the bar: arrows, Enter, Back, Home,
  play/pause, stop, volume, Kodi's info, context and on-screen menus, all
  from the keyboard, with buttons for the mouse. It shows what is playing and
  the last result or error.
- **Typing.** When Kodi shows its on-screen keyboard (a search, say), the
  remote shows a text field: what you type appears on the TV, Enter sends it.
- **The bar.** A Kodi icon while Kodi answers, with a paused mark; hover for
  the title and time. Away from home the icon goes away by itself.
- **The terminal.** Every action also works from `omakodi` in a terminal or
  over ssh, without the shell.

## Requirements

- Omarchy 4 with Quattro shell-plugin support. omakodi itself needs only
  Python 3 and its standard library, which Omarchy already has.
- Kodi on the same network, set up as below.
- For sending links: the SendToKodi add-on; the YouTube add-on is optional.

### Kodi settings

In Kodi, Settings → Services → Control:

- **Allow remote control via HTTP** on. Note the port (8080 by default),
  and set a username and password.
- **Allow remote control from applications on other systems** on. This opens
  the event port (9090), which tells omakodi at once when something starts,
  stops or asks for text. Without it omakodi still works, but checks only
  every 5 seconds and can't offer the text field.

Kodi talks plain HTTP: read [SECURITY.md](SECURITY.md) for what that means.

### Add-ons

- **SendToKodi** (`plugin.video.sendtokodi`) plays links from most video
  sites through yt-dlp. It isn't in Kodi's official repository; install it
  from [its project page](https://github.com/firsttris/plugin.video.sendtokodi).
  Without it, only YouTube links play.
- **YouTube** (`plugin.video.youtube`) plays YouTube links natively. Optional:
  without it, YouTube links go to SendToKodi too.

## Installation

```bash
omarchy plugin add https://github.com/frestina/omakodi.git --enable
```

`--enable` puts the icon on the bar; it asks which section (right by
default). To put it somewhere else later:
`omarchy plugin enable io.github.frestina.omakodi --section tray`.

For a local checkout:

```bash
omarchy plugin add "$(pwd)" --enable
```

Then, from the plugin folder (`~/.config/omarchy/plugins/io.github.frestina.omakodi`):

```bash
./install.sh
```

This is optional. It links the `omakodi` command into `~/.local/bin` (it
must exist already; Omarchy has it on PATH) and prints the next two steps.
It doesn't write the config or touch your Hyprland files.
`./install.sh --uninstall` removes the link and nothing else.

### Config

```bash
omakodi init      # writes ~/.config/omakodi/config.json, mode 600
```

Put your Kodi's address and login in it:

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

- `host`: an IP address or a name your network resolves (an ssh alias won't
  do). Required.
- `httpPort`, `tcpPort`: Kodi's web server and event ports; 8080 and 9090
  if left out.
- `username`, `password`: Kodi's web server login. Leave them out if it has
  none.
- `youtubeMode`, for YouTube links:

  | Mode | YouTube links go to |
  | --- | --- |
  | `smart` (default) | the YouTube add-on, SendToKodi if it fails; straight to SendToKodi for 30 minutes after a failure |
  | `youtube-first` | the YouTube add-on, SendToKodi if it fails |
  | `youtube-only` | the YouTube add-on only |
  | `sendtokodi-only` | SendToKodi only |

The file must stay readable only by you (`chmod 600`); omakodi refuses it
otherwise. `omakodi config` checks it without showing the password, and
`omakodi status` checks that Kodi answers. The shell picks up changes to the
file by itself.

### Keybindings

Not installed for you; add the ones you want to
`~/.config/hypr/bindings.lua`:

```lua
o.bind("SUPER + SHIFT + K", "Kodi remote", "omarchy-shell io.github.frestina.omakodi toggleRemote")
o.bind("SUPER + SHIFT + ALT + K", "Play link on Kodi", "omakodi play --clipboard --notify")
o.bind("SUPER + SHIFT + CTRL + K", "Queue link on Kodi", "omakodi queue --clipboard --notify")
```

| Key | Does |
| --- | --- |
| `SUPER SHIFT + K` | open or close the remote |
| `SUPER SHIFT ALT + K` | play the link on the clipboard |
| `SUPER SHIFT CTRL + K` | queue the link on the clipboard (plays it if nothing is playing) |

These keys are free in Omarchy 4's defaults. The play and queue bindings need
the `omakodi` command on PATH (`./install.sh`), or use the full path to
`bin/omakodi` in the plugin folder.

## Using the remote

Open it with `SUPER SHIFT + K` or a click on the bar icon. It has the
keyboard while it is open, wherever the mouse is; a click outside it, Esc,
the close button or the bar icon closes it.

| Key | Does | Key | Does |
| --- | --- | --- | --- |
| Arrows | move in Kodi's menus | Space | play/pause |
| Enter | select | `x` | stop |
| Backspace | back | `+` `-` `m` | volume up, down, mute |
| `h` | home | `c` | context menu |
| `i` | info | `o` | on-screen menu |
| `f` | fullscreen on/off | `p` / `q` | play / queue the link on the clipboard |
| Esc | close the remote | | |

While a video plays full screen, Left/Right skip about 10 seconds and Up/Down
take Kodi's big step (up to 10 minutes). Holding an arrow there skips once;
in menus it keeps moving.

When Kodi's on-screen keyboard is open, the remote shows a text field with
Kodi's prompt. Type, and the text appears on the TV; Enter sends it; Esc
closes Kodi's keyboard and gives the keys back to the remote. For a password
the field shows dots, and omakodi drops whatever text Kodi sends along with
the request, so it is never shown or reported.

## The terminal

```bash
omakodi status                         # what is playing, as JSON
omakodi play https://video.example.net/clip/7
omakodi queue --clipboard              # the link on the clipboard
omakodi control playpause              # any remote action: up, down, left, right,
                                       # select, back, home, info, context, osd,
                                       # playpause, stop, volup, voldown, mute, fullscreen
omakodi config                         # the config, password hidden
```

`--notify` on `play` and `queue` also shows the result as a notification.

## Known limits

- **Playing replaces Kodi's queue.** `play` starts the item as Kodi's new
  video playlist, so anything queued before is gone. Use queue to keep it.
- **Volume over HDMI-CEC.** When Kodi passes volume to the TV or soundbar
  over CEC, the volume keys work, but the remote's "Volume" reads Kodi's own
  level, which stays at 100%.
- **SendToKodi failures show only on the TV.** omakodi says "Playing on
  Kodi…" once SendToKodi has the link; if yt-dlp then fails (a removed video,
  a login wall), Kodi shows the error.
- **One Kodi.** The config names one box.
- **Same network only.** omakodi talks to Kodi directly; away from home the
  icon disappears and the remote says Kodi isn't answering.

## Compatibility

Tested with:

| | Version |
| --- | --- |
| Omarchy | 4.5.0-3 |
| Quickshell | 0.3.2.r7 |
| Hyprland | 0.56.2 |
| Python | 3.14.8 (the tests also run on 3.12 in CI) |
| Kodi | 21.3 Omega (JSON-RPC 13.5.0) on LibreELEC 12.2.1 |
| YouTube add-on | 7.4.4+unofficial.1 |
| SendToKodi | 0.10.3 |

Other Kodi versions with JSON-RPC 13 (Kodi 20 and later) should work but
haven't been tried.

## Validation and tests

```bash
./tests/run
omarchy plugin validate .
```

The tests run against a fake Kodi (`tests/fakekodi.py`); they never talk to
a real one.

## Update

```bash
omarchy plugin update io.github.frestina.omakodi
```

## Removal

```bash
~/.config/omarchy/plugins/io.github.frestina.omakodi/install.sh --uninstall   # if you ran install.sh
omarchy plugin remove io.github.frestina.omakodi
```

Removing the plugin leaves:

- `~/.config/omakodi/`: your config, **with the Kodi password**. Delete it
  with `rm -r ~/.config/omakodi`.
- `~/.local/state/omakodi/`, if it exists: when the YouTube add-on last
  failed. Safe to delete.
- The keybindings you added to `~/.config/hypr/bindings.lua`.
- `~/.local/bin/omakodi`, as a broken link, if you ran `install.sh` and
  not `--uninstall` before removing; `rm` it.

## Security

Omarchy plugins run as unsandboxed code inside `omarchy-shell`. Review this
repository before enabling it. What omakodi sends where, and where the
password lives: [SECURITY.md](SECURITY.md).

## License

MIT © 2026 Frestina
