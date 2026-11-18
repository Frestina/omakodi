# omakodi

A keyboard remote for Kodi as an Omarchy 4 shell plugin. Public project, MIT.

- **Source of truth:** [SPEC.md](SPEC.md). **Work:** [tickets/README.md](tickets/README.md)
  (status lives only in its tables; next ticket = lowest `todo` with all
  dependencies `done`). Later features: [tickets/BACKLOG.md](tickets/BACKLOG.md).
- **Tests:** `./tests/run` (manifest check, Python unit tests against
  `tests/fakekodi.py`, `omarchy plugin validate`). Must pass before a ticket is done.
- **Commits** start with the ticket number (`007: …`). The repo is public at
  github.com/Frestina/omakodi; push only when the user says so. Tags are never moved.
- **Code:** `bin/omakodi` → `lib/omakodi/` (Python 3 standard library only, run
  with `python3 -I`). QML entry points in the repo root (`Service.qml`,
  `BarWidget.qml`, `Panel.qml`).
- **Public repo hygiene:** fixtures, docs and examples are fictional
  (`kodi.example.lan`, made-up titles). No real addresses, hostnames or account
  names. Live checks against the real box go in `docs/live-checks.local.md`
  (git-ignored).
- **Secrets:** the Kodi password lives only in `~/.config/omakodi/config.json`
  (mode 600). Never print, log or pass it in argv; don't read it into the chat.
  `omakodi config` shows the config with the password hidden.
- **Real box:** `omakodi status` is read-only. Anything that changes what's on
  the TV (control, play, queue) needs the user's go-ahead in that session.
- **Live shell:** the plugin is a symlink in `~/.config/omarchy/plugins`. The
  shell's file watcher doesn't follow it, and its plugin reload reuses
  Quickshell's cached QML, so changed QML only loads after
  `omarchy-restart-shell` (the user's whole bar blinks; not the TV).
- **Skills per ticket:** service/IPC → omarchy-service-ipc; bar widget →
  omarchy-bar-widget; remote panel → omarchy-panel-overlay; QML in general →
  omarchy-qml-patterns; checks → omarchy-plugin-test; plugin not loading →
  omarchy-plugin-debug; demo → omarchy-plugin-demo; release → omarchy-plugin-release
  and omarchy-plugin-publish.
