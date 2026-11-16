# Backlog

Not in v1. Turn an item into a ticket when it is picked up.

## v2

- **Now-playing panel:** artwork (fetched by the daemon into
  `~/.cache/omakodi/`, since Kodi's `/image/` needs the login), seek bar,
  elapsed/total and end time, previous/rewind/play-pause/fast-forward/next,
  the queue (jump to an entry), a details card (plot, stream badges, genres,
  year, studio, rating, cast).
- **Audio track** picker (`Player.SetAudioStream`) and player process info
  (`Input.ExecuteAction` `playerprocessinfo`).
- **Power menu:** Kodi's shutdown menu, reboot, shut down; Wake-on-LAN (MAC
  from `Network.MacAddress`, saved on first connect); turn on the TV and
  soundbar over HDMI-CEC (`CECActivateSource` through the EventServer on UDP
  9777, which JSON-RPC can't run).
- **Text input:** when Kodi asks for text (`Input.OnInputRequested`), the
  remote shows a text field and sends it with `Input.SendText`.

## v3

- **Shortcut buttons:** a few custom buttons (default Movies, TV shows,
  Music), chosen from a live list of Kodi's screens, library sections,
  add-ons and their folders, favourites and sources (`Files.GetDirectory`,
  `Addons.GetAddons`, `Favourites.GetFavourites`, `Files.GetSources`), with
  Kodi's artwork as the icon.
- **Several Kodi boxes:** a list in the config, a switcher in the remote,
  discovery over zeroconf (`_xbmc-jsonrpc-h._tcp`, `avahi-browse`).

## From the ticket 012 live check

- **Play keeps the queue.** `play` is `Player.Open` of one item, which
  replaces Kodi's video playlist: a queue of 4 was gone after one `play`.
  Instead, insert after the playing item (`Playlist.Insert`) and jump to it
  (`Player.GoTo`), or play the item outside the playlist if Kodi allows.
- **Volume with HDMI-CEC audio.** When Kodi forwards volume and mute over
  CEC to a TV or soundbar, `volup`/`voldown`/`mute` work but Kodi's own
  volume stays at 100, so the remote's "Volume 100%" never moves. Hide the
  volume after a step that didn't change it, or say "volume on the TV".
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
