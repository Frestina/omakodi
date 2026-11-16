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

## Ideas

- Report SendToKodi failures too: today `play` says "Playing on Kodi…" at once and
  only the TV shows yt-dlp's error (404, login required). Watching for a player
  that never starts would let the notification say it failed.

- `youtubeMode` as a bar widget setting instead of the config file.
- An Omarchy menu entry ("Play clipboard on Kodi").
- Open local files that Kodi can already reach through a shared folder.
