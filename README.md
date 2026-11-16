# omakodi

[![Built for Omarchy: Plugin](https://raw.githubusercontent.com/tcballard/omarchy-badges/75975e5b5bf75e7ede3764bcd2950046f7abfe2c/badges/v1/omarchy-plugin.svg)](https://github.com/tcballard/omarchy-badges)

A keyboard remote for Kodi: send links to play or queue, drive Kodi's menus from the keyboard, and see what is playing in the bar.

Kinds: service, bar-widget, panel

## GitHub topics

Pair this badge with `omarchy` and `omarchy-plugin` in your GitHub repository's
About topics. The badge does not set topics automatically. Keep other relevant
topics too. This is a community discovery convention, not marketplace approval.

## Requirements

- Omarchy 4 with Quattro shell-plugin support. omakodi itself needs only
  Python 3 (its standard library), which Omarchy already has.
- Kodi with Settings → Services → Control → *Allow remote control via HTTP*
  and *Allow remote control from applications on other systems*.
- For sending links: the SendToKodi add-on, and optionally the YouTube
  add-on.

## Installation

```bash
omarchy plugin add https://github.com/frestina/omakodi.git --enable
```

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

Use an IP address or a name your network resolves (an ssh alias won't do).
`omakodi config` checks the file without showing the password, and
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

These keys are free in Omarchy 4's defaults. The play and queue bindings need
the `omakodi` command on PATH (`./install.sh`), or use the full path to
`bin/omakodi` in the plugin folder.

## Validation and tests

```bash
./tests/run
omarchy plugin validate .
```

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
repository and its dependencies before enabling it.

## License

MIT © 2026 Frestina
