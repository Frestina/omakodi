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

- [ ] Nothing private in the commits since v0.2.0 (history and tree
      searched for the box's address, MAC, hostnames and names); the
      demo media show fictional data only.
- [ ] `manifest.json` 0.3.0, CHANGELOG dated; `tests/run` and the release
      preflight pass.
- [ ] Upgrade from v0.2.0 in a throwaway HOME: a 0.2.0 config and state
      (one box, host-keyed) load and move to box ids; fresh install and
      removal as documented.
- [ ] The user's go-ahead to publish; pushed; CI green on the release
      commit.
- [ ] Annotated tag v0.3.0 on the tested commit, pushed; GitHub release
      with the CHANGELOG's 0.3.0 notes.
