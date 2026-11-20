---
id: 050
title: The soundbar keys don't repeat when held
milestone: M7
depends_on: [044]
---

## Goal

Holding a Soundbar key sends one press, not a stream of them. The user
(2026-11-20): the soundbar keys shouldn't repeat. (044 made them repeat
like Kodi's volume keys; the phone remote has no soundbar volume keys.)

## Scope

- SPEC first: the held-keys rule and the Soundbar row.
- The Soundbar row's `+` and `-` (mouse and keys) send once per press,
  however long they are held. Kodi's volume keys and the arrows keep
  repeating as in 044; mute never repeats.

## Done when

- [x] Unit tests: a held soundbar key sends once; a held Kodi volume key
      and a held arrow still repeat.
- [x] Live, by the user: holding the soundbar keys changes the soundbar
      by one step. *2026-11-20: the user's check passes; mute
      acting once is fine.*
