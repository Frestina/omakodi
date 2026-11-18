---
id: 015
title: Release 0.1.0 on GitHub
milestone: M3
depends_on: [013, 014]
---

## Goal

Public repo on GitHub, tagged v0.1.0 with its release. Each outward step only
after the user says go. The marketplace listing is ticket 022: the user wants
the remote complete before it is listed.

## Done when

- [x] User approved creating github.com/Frestina/omakodi and pushing. *2026-11-18: "go ahead with everything in 015".*
- [x] CI green; release preflight passed (omarchy-plugin-release skill).
      *CI run 44215039719 green on 195ba76; `release_preflight.py --tag v0.1.0`
      READY. Its warnings are manual-review items: CLAUDE.md (agent
      instructions in the repo; look again before 022), install.sh, the QML
      daemon process, demo/screenshot restarting the shell. History searched
      for private details before the first push: none.*
- [x] Fresh install and removal from the public repo, in a throwaway HOME
      with `omarchy-shell` stubbed: `plugin add` cloned 195ba76, its tests
      and validation pass, install.sh links (twice safely) and unlinks,
      `plugin remove` leaves only empty folders. No earlier version, so no
      upgrade path to test.
- [x] Tag v0.1.0 matches `manifest.json`. *Annotated tag a6f89aa on
      195ba76, pushed; release https://github.com/Frestina/omakodi/releases/tag/v0.1.0.
      Private vulnerability reporting on (SECURITY.md points to it).*
