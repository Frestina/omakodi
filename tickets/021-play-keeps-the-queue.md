---
id: 021
title: Play keeps the queue
milestone: M2
depends_on: [004, 005, 020]
---

## Goal

`play` while Kodi plays from its video queue puts the new item right after
the playing one and starts it there, so the rest of the queue still follows
(SPEC "Sending a link"). From the ticket 012 live check (backlog): `play` was
`Player.Open` of one item, which replaced the queue, so a queue of 4 was gone
after one `play`.

## Scope

- When the active player plays from the video playlist (`Player.GetProperties`
  `playlistid` 1, `position` n), `play` does `Playlist.Insert` at n + 1 and
  `Player.Open` of that playlist position. Otherwise (nothing playing, music,
  a video not from the queue) it opens the item as before.
- The YouTube verdict counts progress only for the item at that position:
  when a queued YouTube item fails, Kodi moves on to the next queue item,
  which must not read as the new video playing.
- The fallback takes the failed item's place (`Playlist.Remove`, then insert
  there); if Kodi won't remove it (it is still the playing item), the
  SendToKodi item goes right after it.
- `queue` is unchanged. SPEC, README (the known limit goes) and CHANGELOG.

## Done when

- [x] Unit tests against the fake: with the queue playing at position 2,
      `play` inserts at 3 and opens position 3; outside the queue (no
      playlist, music, bad position, player gone) it opens the item; the
      fallback replaces the failed item, or goes after it when Kodi refuses;
      the next queue item playing isn't taken for the new video.
- [ ] Live, by the user while watching: with a queue playing, `p` on a link
      plays it now, and when it ends (or with `.`) the queue carries on where
      it was.
