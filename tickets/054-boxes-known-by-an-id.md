---
id: 054
title: Kodi boxes known by an id, like the phone remote
milestone: M7
depends_on: [042]
---

## Goal

A saved box is known by an id of its own, as on the phone remote, not by
its address. Two boxes on one address can both be saved, and a box's
settings stay with it when its address changes.

## Scope

- SPEC first ("Kodi boxes", "Files").
- Each saved box gets a random id when it is made; switching, saving,
  deleting and every per-box file (shortcut buttons, YouTube mode and
  failures, MAC address, soundbar finding) go by that id. Existing
  config and state files move over without the user doing anything.
- Editing a box keeps its id, so its settings stay after a change of
  address; the MAC address is kept too (filled in only when empty).
  Deleting a box removes its settings.
- No check for duplicates; "Found on your network" still hides a box
  whose address and port are already saved.
- Test connection and Save use what is in the fields; an untouched
  password field means the saved password, even after an address change
  (as now, and as on the phone).

## Done when

- [ ] Unit tests: the move from host-keyed files, two boxes on one
      address, an address change keeping the settings, delete clearing
      them.
- [ ] Live, by the user: the remote works as before after the move; a
      box renamed and re-addressed keeps its shortcut buttons.
