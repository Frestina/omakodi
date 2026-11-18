# Backlog

Not in v1. Turn an item into a ticket when it is picked up.

## v2

Moved to tickets 023–031 (milestone M5) on 2026-11-18.

## v3

- **Shortcut buttons:** a few custom buttons (default Movies, TV shows,
  Music), chosen from a live list of Kodi's screens, library sections,
  add-ons and their folders, favourites and sources (`Files.GetDirectory`,
  `Addons.GetAddons`, `Favourites.GetFavourites`, `Files.GetSources`), with
  Kodi's artwork as the icon.
- **Several Kodi boxes:** a list in the config, a switcher in the remote,
  discovery over zeroconf (`_xbmc-jsonrpc-h._tcp`, `avahi-browse`).

## From the ticket 012 live check

- **`kind` for add-on items** is `"unknown"` (Kodi's `type` for a plugin
  item); nothing shows it yet. If v2 needs it, derive it from the player
  (`video`/`audio`).

## Ideas

- Report SendToKodi failures too: today `play` says "Playing on Kodi…" at once and
  only the TV shows yt-dlp's error (404, login required). Watching for a player
  that never starts would let the notification say it failed.

- Stopping a YouTube video while its verdict is pending (`x` in the remote
  within 30 s of `play`) reads as a failure and opens it again with
  SendToKodi. The verdict could ignore a stop the user sent.
- `youtubeMode` as a bar widget setting instead of the config file.
- An Omarchy menu entry ("Play clipboard on Kodi").
- Open local files that Kodi can already reach through a shared folder.
