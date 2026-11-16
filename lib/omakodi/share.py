"""Sending a link to Kodi: play or queue (SPEC "Sending a link")."""

from typing import NamedTuple, Optional

from . import links, route
from .control import active_player
from .errors import USAGE, OmakodiError
from .rpc import KodiCallError

VIDEO_PLAYLIST = 1


class Target(NamedTuple):
    path: str  # the plugin:// item to open
    route: Optional[route.Route]  # None for non-YouTube links
    video_id: Optional[str]
    url: str


def addon_enabled(kodi, addon_id):
    try:
        got = kodi.call("Addons.GetAddonDetails", {"addonid": addon_id, "properties": ["enabled"]})
    except KodiCallError:
        return False  # Kodi says it doesn't exist
    addon = got.get("addon") if isinstance(got, dict) else None
    return isinstance(addon, dict) and addon.get("enabled") is True


def how(r):
    """' with SendToKodi (the YouTube add-on failed recently)' when the usual add-on wasn't used."""
    if r is None or r.note is None:
        return ""
    name = "the YouTube add-on" if r.youtube_addon else "SendToKodi"
    return f" with {name} ({r.note})"


class Sender:
    """Plays or queues links on one Kodi box.

    ``verdict`` (ticket 005) decides whether the YouTube add-on started; until
    then, YouTube links are opened without watching.
    """

    def __init__(self, kodi, youtube_mode, health, verdict=None):
        self.kodi = kodi
        self.youtube_mode = youtube_mode
        self.health = health
        self.verdict = verdict

    def target(self, text):
        url = links.extract_url(text)
        if url is None:
            raise OmakodiError("no link found", "the text has no http(s) link", USAGE)
        video_id = links.youtube_video_id(url)
        if video_id is None:
            if not addon_enabled(self.kodi, links.SENDTOKODI_ADDON):
                raise OmakodiError("SendToKodi isn't installed",
                                   "install it in Kodi to play links from websites")
            return Target(links.sendtokodi_path(url), None, None, url)
        r = route.choose(
            self.youtube_mode,
            has_youtube=addon_enabled(self.kodi, links.YOUTUBE_ADDON),
            has_sendtokodi=addon_enabled(self.kodi, links.SENDTOKODI_ADDON),
            failed_recently=self.health.failed_recently(),
        )
        if r is None:
            raise OmakodiError("SendToKodi isn't installed",
                               "and neither is the YouTube add-on; install one in Kodi")
        path = links.youtube_path(video_id) if r.youtube_addon else links.sendtokodi_path(url)
        return Target(path, r, video_id, url)

    def open(self, path):
        self.kodi.call("Player.Open", {"item": {"file": path}})

    def play(self, text, progress=None):
        """Play the link now. Returns the message for the user.

        ``progress(message)`` reports intermediate steps (the fallback).
        """
        t = self.target(text)
        r = t.route
        if r is None or not r.youtube_addon or not r.fallback or self.verdict is None:
            self.open(t.path)
            return f"Playing on Kodi{how(r)}…"
        outcome = self.verdict(self.kodi, t)
        if outcome == "playing":
            self.health.clear()
            return "Playing on Kodi"
        if outcome == "undecided":
            return "Still loading on Kodi; Kodi shows an error if YouTube can't play it"
        self.health.record_failure()
        if progress:
            progress("The YouTube add-on couldn't play it, trying SendToKodi…")
        self.open(links.sendtokodi_path(t.url))
        return "Playing on Kodi with SendToKodi (the YouTube add-on couldn't play it)…"

    def queue(self, text, progress=None):
        """Add the link to the queue, or play it when nothing is playing."""
        if active_player(self.kodi) is None:
            return self.play(text, progress)
        # A queued video starts later, so there is no fallback; smart mode uses
        # what earlier plays taught it.
        t = self.target(text)
        self.kodi.call("Playlist.Add", {"playlistid": VIDEO_PLAYLIST, "item": {"file": t.path}})
        props = self.kodi.call("Playlist.GetProperties", {"playlistid": VIDEO_PLAYLIST, "properties": ["size"]})
        size = props.get("size") if isinstance(props, dict) else None
        count = f" ({size} in queue)" if isinstance(size, int) else ""
        return f"Queued on Kodi{how(t.route)}{count}"
