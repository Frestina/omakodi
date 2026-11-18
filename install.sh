#!/usr/bin/env bash
# Optional setup for omakodi (SPEC "Keybindings"). It links bin/omakodi into
# ~/.local/bin so keybindings and terminals find `omakodi`, then prints the
# config template and the suggested keybindings. It never writes the config
# or the password, and never edits Hyprland files.
#
#   ./install.sh               link the command (safe to run again)
#   ./install.sh --uninstall   remove that link, and nothing else
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
src="$root/bin/omakodi"
dir="$HOME/.local/bin"
dest="$dir/omakodi"

# True when $dest is a link that ends at this checkout's bin/omakodi.
ours() {
  [[ -L $dest ]] && [[ "$(readlink -f "$dest")" == "$(readlink -f "$src")" ]]
}

uninstall() {
  if ours; then
    rm -- "$dest"
    echo "removed $dest"
  elif [[ -L $dest || -e $dest ]]; then
    echo "install.sh: $dest isn't a link to $src, leaving it alone" >&2
    return 1
  else
    echo "nothing to remove: $dest doesn't exist"
  fi
  cat <<EOF

Still there, yours to remove:
  ~/.config/omakodi/      the config with the Kodi password (rm -r it)
  ~/.local/state/omakodi/ (when the YouTube add-on last failed; titles of queued links)
  ~/.cache/omakodi/       (posters and thumbnails of what played)
  the keybindings you added to ~/.config/hypr/bindings.lua
EOF
}

link() {
  if ours; then
    echo "$dest already links to $src"
  elif [[ -L $dest && ! -e $dest ]]; then
    ln -sfn -- "$src" "$dest"
    echo "replaced a broken link: $dest -> $src"
  elif [[ -L $dest || -e $dest ]]; then
    echo "install.sh: $dest exists and isn't a link to $src, leaving it alone" >&2
    echo "Remove it yourself and run this again." >&2
    return 1
  elif [[ ! -d $dir ]]; then
    echo "install.sh: $dir doesn't exist" >&2
    echo "Create it (mkdir -p ~/.local/bin) and run this again; Omarchy has it on PATH." >&2
    return 1
  else
    ln -s -- "$src" "$dest"
    echo "linked $dest -> $src"
  fi
  case ":$PATH:" in
    *":$dir:"*) ;;
    *) echo "note: $dir isn't on this shell's PATH" ;;
  esac
}

next_steps() {
  local template
  template="$(python3 -I -c '
import json, sys
sys.path.insert(0, sys.argv[1])
from omakodi.config import TEMPLATE
print(json.dumps(TEMPLATE, indent=2))
' "$root/lib")"

  cat <<EOF

Next:

1. Run \`omakodi init\`. It writes this template to
   ~/.config/omakodi/config.json with mode 600; put your Kodi's address,
   username and password in it:

$(sed 's/^/     /' <<<"$template")

   \`omakodi config\` checks it (the password stays hidden),
   \`omakodi status\` checks that Kodi answers.

2. Add the keybindings you want to ~/.config/hypr/bindings.lua:

     o.bind("SUPER + SHIFT + K", "Kodi remote", "omarchy-shell io.github.frestina.omakodi toggleRemote")
     o.bind("SUPER + SHIFT + ALT + K", "Play link on Kodi", "omakodi play --clipboard --notify")
     o.bind("SUPER + SHIFT + CTRL + K", "Queue link on Kodi", "omakodi queue --clipboard --notify")

Undo with: $root/install.sh --uninstall
EOF
}

case "${1:-}" in
  "") link; next_steps ;;
  --uninstall) uninstall ;;
  -h|--help) sed -n '2,8s/^# \{0,1\}//p' "$0" ;;
  *) echo "usage: install.sh [--uninstall]" >&2; exit 2 ;;
esac
