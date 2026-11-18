---
id: 037
title: Release 0.2.0 on GitHub
milestone: M5
depends_on: [023, 024, 025, 026, 027, 028, 029, 030, 031, 032, 033, 034, 035, 036]
---

## Goal

The M5 remote on GitHub as v0.2.0: push `main`, tag and release. The
marketplace listing stays with 022 (the user: wait).

## Done when

- [x] Nothing private in the commits since v0.1.0; `preview.png` shows
      the new remote (fictional data). *History and tree searched for the
      box's address, MAC, hostnames, names: none. Preview retaken with the
      crop 560 px high.*
- [x] `manifest.json` 0.2.0, CHANGELOG dated; `tests/run` and the release
      preflight pass. *`release_preflight.py --tag v0.2.0` READY; its
      warnings are the same manual-review items as 0.1.0.*
- [x] Pushed; CI green on the release commit. *Run 44297068274 green on
      4d362df.*
- [x] Fresh install, upgrade from v0.1.0 and removal, in a throwaway HOME.
      *`omarchy-shell` stubbed: `plugin add` cloned 4d362df, its tests
      pass; reset to v0.1.0 with a 0.1.0 config and state, `plugin update`
      fast-forwarded to 0.2.0, the old config loads (new keys default) and
      the state stays; install.sh links twice and unlinks; `plugin remove`
      leaves only the config and state, as documented.*
- [x] Annotated tag v0.2.0 on the tested commit, pushed; GitHub release
      with the CHANGELOG's 0.2.0 notes. *Tag 0918a82 on 4d362df;
      https://github.com/Frestina/omakodi/releases/tag/v0.2.0.*
