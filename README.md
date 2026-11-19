# omakodi

[![Built for Omarchy: Plugin](https://raw.githubusercontent.com/tcballard/omarchy-badges/75975e5b5bf75e7ede3764bcd2950046f7abfe2c/badges/v1/omarchy-plugin.svg)](https://github.com/tcballard/omarchy-badges)

A keyboard remote for Kodi on Omarchy. Send a link from the clipboard to play
or queue it, drive Kodi's menus from the keyboard, and see what is playing in
the bar, without picking up a phone.

Kinds: service, bar-widget, panel

## What it does

- **Play or queue a link.** Copy a video link, press a key, and Kodi plays
  it, or adds it to its queue. Playing while the queue plays keeps the
  queue: the link plays now and the queue carries on after it. YouTube
  links go to the YouTube add-on, with SendToKodi as the fallback;
  everything else goes to SendToKodi. A notification says what happened.
- **The remote.** A small panel below the bar: arrows, Enter, Back, Home,
  play/pause, stop, next/previous in the queue, volume, Kodi's info,
  context and on-screen menus, all from the keyboard, with buttons for the
  mouse. It shows what is playing and the last result or error.
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
  every 5 seconds and can't offer the text field. It also opens Kodi's
  EventServer (UDP 9777), which "Turn on the soundbar" needs.

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
  if left out. `eventPort`: Kodi's EventServer, 9777 if left out.
- `username`, `password`: Kodi's web server login. Leave them out if it has
  none.
- `youtubeMode`, for YouTube links:

  | Mode | YouTube links go to |
  | --- | --- |
  | `smart` (default) | the YouTube add-on, SendToKodi if it fails; straight to SendToKodi for 30 minutes after a failure |
  | `youtube-first` | the YouTube add-on, SendToKodi if it fails |
  | `youtube-only` | the YouTube add-on only |
  | `sendtokodi-only` | SendToKodi only |

  The config file's `youtubeMode` is only where it starts: choose the mode
  in the remote's **Settings** (in the ☰ menu, or `S`), as on a phone
  remote. The choice is kept for your box and used for every link you send,
  from the remote and the play keybindings alike; `omakodi config` shows
  which mode is in use and where it came from.
- `mac`, `wakeOnLan`: for waking the box, see [Wake-on-LAN](#wake-on-lan).
  Both optional.

The file must stay readable only by you (`chmod 600`); omakodi refuses it
otherwise. `omakodi config` checks it without showing the password, and
`omakodi status` checks that Kodi answers. The shell picks up changes to the
file by itself.

#### Several Kodi boxes

The remote can keep several boxes and switch between them (see [Kodi
boxes](#kodi-boxes)); it writes them to the same file as a list, each
with its own name, login, ports, `mac` and `wakeOnLan`:

```json
{
  "youtubeMode": "smart",
  "boxes": [
    {"name": "Living room", "host": "kodi.example.lan", "username": "kodi", "password": "example-password"},
    {"name": "Bedroom", "host": "bedroom.example.lan", "wakeOnLan": false}
  ]
}
```

A file with one box at the top, as above, keeps working; the remote turns
it into a list the first time it saves a box. Every box needs its own
`host`.

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
| `.` | next in the queue | `,` | previous in the queue |
| `<` | rewind (press again: faster) | `>` | fast-forward (press again: faster) |
| `u` | the queue (on the now-playing page) | `d` | the details (on the now-playing page) |
| `a` | choose the audio track | | |
| `I` (Shift `i`) | Kodi's player info on the TV | `n` | the now-playing page, or back |
| `P` (Shift `p`) | the power menu | `w` | wake up the box (Wake-on-LAN) |
| `s` | turn on the soundbar | `9` / `0` | soundbar down / up (HDMI-CEC) |
| `M` (Shift `m`) | the ☰ menu | `b` | Manage Kodi boxes |
| `S` (Shift `s`) | Settings | Esc | close the remote (from a menu or page: back) |
| `1`–`5` | the shortcut buttons, from the left | `e` then `1`–`5` | change that shortcut button |
| `k` | type text into Kodi's keyboard | | |

While a video plays full screen, Left/Right skip about 10 seconds and Up/Down
take Kodi's big step (up to 10 minutes). Holding an arrow there skips once;
in menus it keeps moving.

The remote is laid out like a phone remote. At the top, the ☰ menu
button, the name of your Kodi box with **Connected**, **Offline** or
**Connecting…** under it (and, while it is offline, why and what to
check), the power button and close. Then the shortcut strip, then volume,
then a row of actions (audio track, fullscreen, info, type text, player
info), then a big D-pad (hold or right-click OK for the context menu).
Held with the mouse, the arrows and volume keys repeat like a real
remote's. What
plays sits at the bottom, as on a phone remote: a thin line for how far it
is, its thumbnail, title and subtitle, and stop, play/pause and next, with
its poster blurred behind the whole remote. Click it, or press `n`, for
the now-playing page: the artwork large, a seek bar (click or drag to
jump; the mouse wheel jumps 10 seconds) with the time played, "Paused" or
the speed, and the length and when it ends under it; then previous,
rewind, play/pause, fast-forward and next. Space, `<` `>`, `.` `,` and the
volume keys work there; Esc or `n` goes back to the remote, and the page
closes by itself when playback stops. Press play/pause (Space) to go back
to normal speed after rewinding or fast-forwarding.

The page's Queue button, or `u`, opens the queue: the playing one in the
accent colour, Up/Down choose, Enter (or a click) plays that one, Delete
(or its ×) takes it out of the queue, Esc or Close closes it.

The page's Details button, or `d`, shows what Kodi knows about what
plays, laid out as on a phone remote: the title, the **Overview** (the
whole plot), badges for the picture and sound (4K, HEVC, Dolby Vision,
DD+, 5.1 …), **Info** with a row per field (channel, genre, show, date,
studio, rating, age rating, runtime, director, writer, country) and the
**Cast** as cards with photos. The wheel or Up/Down scroll it,
Left/Right the cast. Library movies and episodes have most of this; a
YouTube video has its channel, date, rating, runtime and description.
Kodi's own info screen stays on `i`.

When what plays has two or more audio tracks (languages, a commentary), a
button shows the playing one, e.g. "English · AC3 5.1 · 1/3"; it, or `a`,
opens the list of tracks: Up/Down choose, Enter (or a click) plays that
one, and `a` or Esc closes the list. The dashboard button, or `I`, opens Kodi's player
info on the TV (codecs, resolution, dropped frames); press it again to close
it.

The ☰ button, a click on the box's name, or `M`, opens the menu: your
Kodi boxes (click one to switch to it), **Manage Kodi boxes**,
**Settings**, and omakodi's version at the bottom. Up/Down and Enter, or a
click; Esc closes it.

The power button, or `P`, opens the power menu, in a phone remote's order:
**Wake up (Wake-on-LAN)**, **Turn on soundbar (HDMI-CEC)**, **Kodi power
menu** (Kodi's own, on the TV), then **Reboot** and **Shut down** (only
when Kodi allows them). It is there while Kodi isn't answering too: Wake
up is how it comes back. Reboot and Shut down ask first, "Reboot Living
room?", with **Cancel** and **Reboot**: the cursor starts on Cancel, so
press Right and Enter, or click Reboot, to go ahead; Esc cancels. After a
shut down the remote says Kodi is off, and after a reboot that it is
restarting, until Kodi answers again.

### Shortcut buttons

Under the top bar, a strip of five buttons: **Home, Movies, TV shows,
Music** and **Send a link** at first. A click (or `1` to `5`) opens that
screen on the TV. Send a link opens a small dialog: paste or type a link
(it starts with the one on the clipboard), then **Play** (Enter) or
**Queue** (Shift+Enter).

Right-click a button, hold it, or press `e` and its number to change it:

- **Choose from Kodi…** lists what your box has, live: Kodi's screens, the
  video and music library sections, your add-ons (open one to pick one of
  its folders, then **Use this folder**), favourites and sources.
- **Use "Send a link"** makes it the Send a link button.
- **Change icon**: the artwork Kodi has for it, or one of about 70
  built-in icons.
- Or type a Kodi path or add-on, such as `plugin://plugin.video.youtube`,
  and **Save**. **Reset** puts the button back.

The buttons are kept per box. `omakodi shortcut 2` opens button 2 from a
terminal.

### Kodi boxes

**Manage Kodi boxes** in the ☰ menu, or `b`, opens **Kodi boxes**, as on
a phone remote (the menu itself lists the saved boxes to switch between):

- **Saved**: your boxes, the one in use marked. Click one (or Enter) to
  switch to it; the pencil (or `e`) edits it.
- **Found on your network**: Kodi boxes that announce themselves
  (zeroconf, through `avahi-browse` from the `avahi` package with
  `avahi-daemon` running) and aren't saved yet. Click one to add it: the
  editor opens with its name, address and ports. Nothing, no login, is
  sent to a found box before you add it.
- **Add manually**: an empty editor.

The editor has Name, IP address or hostname, Web port, Live port (TCP),
Username, Password, MAC address, the Kodi setup help, **Test connection**
("✓ Kodi 21.3", or what is wrong; an empty name or MAC address is filled
from Kodi's answer), **Delete** and **Save**. A saved password is never
shown: the field says one is saved, and stays as it is unless you type a
new one. Saving writes `~/.config/omakodi/config.json` (mode 600).

Switching moves everything to that box: the remote, the bar, the play and
queue keybindings and `omakodi` in the terminal (`omakodi box Bedroom`
switches from there, `omakodi boxes` lists them). Each box keeps its own
shortcut buttons, YouTube mode, MAC address and soundbar finding. The
remote's title names the box in use, and with several boxes the bar's
tooltip does too.

### Settings

**Settings** in the ☰ menu, or `S`, opens a page over the
remote like a phone remote's. Under *Sharing*, *YouTube links* chooses
which add-on plays the YouTube links you send to your box: **Smart**,
**YouTube add-on first**, **SendToKodi only** or **YouTube add-on only**,
each with a line on what it does. Up/Down and Enter, or a click, choose
one; it is saved at once. In Smart mode, after the YouTube add-on failed,
it says until when SendToKodi is used, with **Try the YouTube add-on
again**. Esc, Backspace or the back arrow go back to the remote. Settings
work while Kodi is off too.

### Volume: Kodi's own and the soundbar's

`+`, `-` and `m` change **Kodi's own volume** and mute it, a step at a
time as Kodi's own keys do (Kodi's *Volume control steps* setting: 90
steps by default, so 1% a step);
Kodi's volume bar on the TV moves with it. Under them, a slim **Soundbar** row (`9` down, `0` up)
sends Kodi's volume keys, which Kodi passes to the TV or soundbar over
HDMI-CEC when it is set up to. There is no soundbar level or slider: Kodi
can't read it. On a box without CEC volume control those keys change
Kodi's own volume too; the remote notices the first time and hides the
row. `omakodi volume 60` sets Kodi's own level from the terminal. With
audio passthrough on, Kodi's own volume does nothing.

### Turn on the soundbar

"Turn on the soundbar" in the power menu, or `s`, makes Kodi the active
HDMI source over CEC. With Kodi's CEC setting *Force AVR to wake up when
Kodi is activated* on (Settings → System → Input → Peripherals → CEC
adapter), that wakes the soundbar or AV receiver; a TV that is on switches
to Kodi. Whether a TV in standby comes on is up to the TV. It needs Kodi on
(the box, not the TV) and *Allow remote control from applications on other
systems*, which opens Kodi's EventServer (UDP 9777). The EventServer gives
no answer, so the remote says "Asked Kodi to turn on the soundbar" either
way; if nothing happens, check those two settings.

### Wake-on-LAN

**Wake up (Wake-on-LAN)** in the power menu (or `w`; `omakodi wake` in
the terminal) turns the box on; `"wakeOnLan": false` in the config hides
it. It sends a
Wake-on-LAN packet to your network, and Kodi answers again once the box
has started, usually within a minute. For it to work:

- The box must support Wake-on-LAN and have it on, usually in its BIOS or
  firmware settings. **A Raspberry Pi can't be woken this way**; nor can
  most boxes on Wi-Fi.
- It must be on a cable, on the same network as this computer.
- omakodi must have seen Kodi on once: while Kodi answers, it reads the
  box's MAC address and keeps it in `~/.local/state/omakodi/mac.json`
  under the box's `host` (`{"hosts": {"kodi.example.lan":
  "aa:bb:cc:dd:ee:ff"}}`). Change `host` and it reads it again.

Set `"mac": "aa:bb:cc:dd:ee:ff"` in the config to use another address
(say, the box's wired one while Kodi reports Wi-Fi's). For a box that
can't be woken, `"wakeOnLan": false` hides the button and stops reading the
address.

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
                                       # playpause, stop, next, previous, rewind, fastforward,
                                       # volup, voldown, mute (Kodi's own volume),
                                       # soundbarup, soundbardown (HDMI-CEC),
                                       # fullscreen, playerinfo,
                                       # powermenu, reboot, shutdown (no second ask here),
                                       # soundbaron (turn on the soundbar over HDMI-CEC)
omakodi seek 12:34                     # jump to a position (seconds, MM:SS, H:MM:SS)
omakodi audio 1                        # another audio track (the index from status)
omakodi wake                           # turn the box on (Wake-on-LAN)
omakodi volume 60                      # Kodi's own volume (not the TV's or soundbar's)
omakodi config                         # the config, password hidden
omakodi boxes                          # the Kodi boxes, * the one in use
omakodi box Bedroom                    # switch boxes (by name or address)
```

`--notify` on `play` and `queue` also shows the result as a notification.

## Known limits

- **No soundbar level.** Kodi can't read the TV's or soundbar's volume
  over CEC, so the soundbar keys step it blind; the remote's "Volume" is
  Kodi's own.
- **SendToKodi says that it failed, not why.** When SendToKodi can't play
  a link (a removed video, a login wall), the remote and the notification
  say "SendToKodi couldn't play it", up to a minute after you sent it; the
  reason is on the TV only (Kodi doesn't pass it on). A link still loading
  after a minute is reported as "still opening it".
- **A stop from Kodi's own remote looks like a failure.** Stop a YouTube
  video with `x` (or `omakodi control stop`) in its first 30 seconds and
  omakodi leaves it stopped; stop it with Kodi's own remote and omakodi
  can't tell that from the add-on failing, so it tries SendToKodi.
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
- `~/.local/state/omakodi/`, if it exists: the box in use and, for each
  box, when the YouTube add-on last failed, the YouTube mode chosen in
  Settings, its MAC address for Wake-on-LAN, whether its soundbar keys
  reach the TV and its shortcut buttons; when you last stopped a video
  through omakodi, and the titles of the last 200 links you queued.
  Safe to delete.
- `~/.cache/omakodi/`: posters and thumbnails of what played and Kodi's
  art for the shortcut buttons (at most 30).
  Safe to delete.
- The keybindings you added to `~/.config/hypr/bindings.lua`.
- `~/.local/bin/omakodi`, as a broken link, if you ran `install.sh` and
  not `--uninstall` before removing; `rm` it.

## Security

Omarchy plugins run as unsandboxed code inside `omarchy-shell`. Review this
repository before enabling it. What omakodi sends where, and where the
password lives: [SECURITY.md](SECURITY.md).

## License

MIT © 2026 Frestina
