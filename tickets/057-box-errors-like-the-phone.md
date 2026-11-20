---
id: 057
title: A box's address, MAC and Test connection errors like the phone remote
milestone: M7
depends_on: [053, 054]
---

## Goal

The three follow-ups from 053, which the user OK'd (2026-11-20).

## Scope

- SPEC first ("Kodi boxes", "Wake-on-LAN", "Messages").
- **A bad MAC address** in the config no longer breaks the whole config:
  the box works, and waking it says "Invalid MAC address for <box>" (as
  the phone remote). The editor still refuses a bad one on Save.
- **The editor refuses an address that can't be one** (`kodi..lan`, one
  with a port in it) on Save and on Test connection, with the same check
  `rpc.is_address` makes, instead of the box saying "Bad address" later.
- **Test connection's errors** in the phone remote's words (read how its
  box screen words them, read-only), with the box's name where it has
  one; "✓ Kodi 21.3" stays.

## Done when

- [ ] Unit tests: a config with a bad MAC loads and waking says so; the
      editor refusing bad addresses (Python and Boxes.js alike); each
      Test connection error's wording.
- [ ] Live, by the user: Test connection with a wrong password and a bad
      address reads like the phone; waking with a bad MAC in the config.
