---
id: 001
title: Config and credentials
milestone: M1
depends_on: []
---

## Goal

`omakodi` reads `~/.config/omakodi/config.json` and refuses anything unsafe or
malformed with the exact wording from SPEC "Errors".

## Scope

- `bin/omakodi` shim: runs `python3 -I` with the repo's `lib/` on `sys.path`,
  resolving its own path through symlinks (it will be linked into `~/.local/bin`).
- `lib/omakodi/config.py`: load, defaults (ports 8080/9090, `youtubeMode`
  `smart`), type checks, the mode/owner check when a password is present.
  `OMAKODI_CONFIG` overrides the path (tests, demo).
- `lib/omakodi/errors.py`: one exception type carrying wording and exit code.
- `omakodi --help`, usage errors exit 2.
- `tests/run` runs `python3 -I -m unittest discover -s tests`.

## Done when

- [x] Missing file → `not configured`, exit 3.
- [x] Not JSON, missing `host`, wrong types, unknown `youtubeMode` → `bad config`, exit 3.
- [x] Password with mode 0640/0604 → `config readable by others` and the `chmod 600` fix, exit 3; no password → any mode accepted.
- [x] No error message or repr ever contains the password (tested).
- [x] `bin/omakodi` works when called through a symlink.
