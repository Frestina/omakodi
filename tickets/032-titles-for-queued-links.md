---
id: 032
title: Titles for queued links
milestone: M5
depends_on: [025]
---

## Goal

A link queued with omakodi shows its title in the remote's queue, not
"play". Kodi has no title for an add-on item until it plays, and JSON-RPC
can't set one (`Playlist.Add` takes a file, not a label). Found in the
ticket 025 live check.

## Scope

- The user chose (2026-11-18) to ask YouTube: before queueing a YouTube
  link, `queue` asks YouTube's oEmbed endpoint (`https://www.youtube.com/oembed`,
  no key, no login; HTTPS, a short timeout, a bounded answer) for the title.
  Other links, and YouTube when that fails, get a label from the link
  (host and path).
- The title is kept in `~/.local/state/omakodi/titles.json` (600, the 200
  most recent) under a hash of the queued item, because `omakodi queue`
  from a keybinding runs outside the daemon.
- The daemon's queue read asks for each entry's `file` only to look up that
  hash, for entries Kodi has no title for; the file never leaves the
  daemon. SPEC, SECURITY.md ("What omakodi talks to", what it writes).

## Done when

- [ ] Unit tests: the oEmbed request and answer handling (no network: a
      stub), the fallback label, the store's bounds and mode, the queue
      using a stored title only where Kodi has none, the file never in the
      state.
- [ ] Live, by the user: queue a YouTube link; the queue shows its title.
