---
id: 013
title: Demo and screenshot
milestone: M3
depends_on: [012, 017, 018, 019]
---

## Goal

A repeatable demo against the fake Kodi and a marketplace screenshot with
fictional data. Use the omarchy-plugin-demo skill.

## Done when

- [x] `demo/run` starts the fake Kodi with a fictional library and points omakodi at it through `OMAKODI_CONFIG`, without touching the real config.
- [x] `preview.png` shows the bar widget playing and the remote open, with fictional titles only.
- [x] `demo/run -- demo/screenshot` restores shell.json, the workspace and
      the normal shell by itself. *2026-11-18: the first run, piped through
      `head`, died of SIGPIPE after restarting the shell: shell.json and the
      shell were back, the workspace and the backup were fixed by hand. The
      restore now ignores SIGPIPE and signals. Second run, same day, with
      the user's go-ahead: exit 0, shell.json sha256-identical (same mode
      and mtime), workspace 1, one shell, daemon on the real config, no
      backup or runtime files left.*
