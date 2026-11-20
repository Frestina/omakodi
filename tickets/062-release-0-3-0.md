---
id: 062
title: Release 0.3.0 on GitHub
milestone: M8
depends_on: [061]
---

## Goal

M6, M7 and the follow-ups (038–061) on GitHub as v0.3.0: push `main`,
tag and release, as 037 did for 0.2.0. The marketplace listing stays with
022 (the user wants to use the remote a while first).

## Done when

- [x] Nothing private in the commits since v0.2.0 (history and tree
      searched for the box's address, MAC, hostnames and names); the
      demo media show fictional data only. *69 commits and the tree
      (images' bytes too) searched: none; only fictional MACs and
      `example` addresses. `preview.png` and `docs/remote.gif` show
      `kodi.example.lan` and the made-up film.*
- [x] `manifest.json` 0.3.0, CHANGELOG dated; `tests/run` and the release
      preflight pass. *`omakodi --version` said 0.1.0: now 0.3.0, with a
      test. 452 tests pass; `release_preflight.py` READY on 13b456a (the
      tag check waits for the tag); its 9 warnings are manual-review
      items (installer, QML processes, CLAUDE.md).*
- [x] Upgrade from v0.2.0 in a throwaway HOME: a 0.2.0 config and state
      (one box, host-keyed) load and move to box ids; fresh install and
      removal as documented. *`omarchy-shell` stubbed: `plugin add`
      cloned 13b456a, its tests pass, `omakodi init` writes mode 600.
      Reset to v0.2.0 with a 0.2.0 config (one box, an extra key) and
      mac, volume, shortcuts, box and titles state by host; `plugin
      update` fast-forwarded, the daemon gave the box an id: config
      still 600 with everything kept, MAC, volume keys, YouTube mode and
      the shortcut read back by id. install.sh links twice and unlinks;
      `plugin remove` leaves only the config and state, as documented.*
- [ ] The user's go-ahead to publish; pushed; CI green on the release
      commit.
- [ ] Annotated tag v0.3.0 on the tested commit, pushed; GitHub release
      with the CHANGELOG's 0.3.0 notes.
