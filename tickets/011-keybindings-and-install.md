---
id: 011
title: Keybindings and install
milestone: M2
depends_on: [010]
---

## Goal

A new user can install omakodi, link the command and add three keybindings
from the README alone.

## Scope

- Choose suggested keys after checking Omarchy's default bindings and the
  common plugin bindings for clashes; write them into SPEC "Keybindings".
- `install.sh` (optional, explicit): link `bin/omakodi` into `~/.local/bin`,
  print the config template and the bindings; `--uninstall` removes only what
  it added. Never writes the password or edits Hyprland files.
- `omakodi init`: writes a config template with mode 600 if none exists.

## Done when

- [x] Fresh-user walkthrough on this machine with a throwaway `HOME` for the command parts.
- [x] `install.sh --uninstall` leaves nothing it created.
- [x] The README lists what stays after `omarchy plugin remove`.
