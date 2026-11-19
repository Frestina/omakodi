"""Sending a link to Kodi: play or queue (SPEC "Sending a link")."""

from typing import NamedTuple, Optional

from . import links, messages as say, route
from .youtubemode import youtube_mode
from .control import active_player
from .errors import USAGE, OmakodiError
from .rpc import Kodi, KodiCallError
from .state import StopNote, YoutubeHealth
from .titles import TitleStore, youtube_title
from .titles import link_label as links_label
from .verdict import FAILED, PLAYING, STOPPED, UNDECIDED, SendToKodiWatch, Verdict

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

    def __init__(self, kodi, youtube_mode, health, verdict=None, titles=None, youtube_title=None,
                 sendtokodi_watch=None, box=say.DEFAULT_BOX):
        self.kodi = kodi
        self.box = box  # the box's name, in every message (SPEC "Messages")
        self.youtube_mode = youtube_mode
        self.health = health
        self.verdict = verdict
        self.sendtokodi_watch = sendtokodi_watch  # SPEC "Sending a link" step 6
        self.titles = titles  # TitleStore, or None: queued links keep Kodi's label
        self.youtube_title = youtube_title  # video id -> title or "" (ticket 032)

    def title_for(self, t):
        """A title for a queued link: YouTube's for a YouTube video, else the link's host and path."""
        if t.video_id:
            title = self.youtube_title(t.video_id) if self.youtube_title else ""
            return title or f"YouTube video {t.video_id}"
        return links_label(t.url)

    def target(self, text):
        url = links.extract_url(text)
        if url is None:
            raise OmakodiError("no link found", "the text has no http(s) link", USAGE)
        video_id = links.youtube_video_id(url)
        if video_id is None:
            if not addon_enabled(self.kodi, links.SENDTOKODI_ADDON):
                raise OmakodiError(say.no_sendtokodi(self.box))
            return Target(links.sendtokodi_path(url), None, None, url)
        r = route.choose(
            self.youtube_mode,
            has_youtube=addon_enabled(self.kodi, links.YOUTUBE_ADDON),
            has_sendtokodi=addon_enabled(self.kodi, links.SENDTOKODI_ADDON),
            failed_recently=self.health.failed_recently(),
        )
        if r is None:
            raise OmakodiError(say.no_addon(self.box))
        path = links.youtube_path(video_id) if r.youtube_addon else links.sendtokodi_path(url)
        return Target(path, r, video_id, url)

    def next_slot(self):
        """The queue position just after the video playing, or None when
        nothing plays or what plays isn't from the video queue."""
        player = active_player(self.kodi)
        if player is None:
            return None
        try:
            props = self.kodi.call("Player.GetProperties",
                                   {"playerid": player, "properties": ["playlistid", "position"]})
        except KodiCallError:
            return None  # the player went away meanwhile
        props = props if isinstance(props, dict) else {}
        pos = props.get("position")
        if props.get("playlistid") != VIDEO_PLAYLIST or type(pos) is not int or pos < 0:
            return None
        return pos + 1

    def open(self, path, slot=None):
        """Play ``path`` now. With a ``slot`` it goes into the queue there and
        plays from it, so the rest of the queue follows; ``Player.Open`` of a
        lone item would replace the queue."""
        if slot is None:
            self.kodi.call("Player.Open", {"item": {"file": path}})
            return
        self.kodi.call("Playlist.Insert", {"playlistid": VIDEO_PLAYLIST, "position": slot, "item": {"file": path}})
        self.kodi.call("Player.Open", {"item": {"playlistid": VIDEO_PLAYLIST, "position": slot}})

    def replace(self, path, slot):
        """Play ``path`` in place of the queue item at ``slot`` (the fallback).
        Returns the slot it went to."""
        if slot is not None:
            try:
                self.kodi.call("Playlist.Remove", {"playlistid": VIDEO_PLAYLIST, "position": slot})
            except KodiCallError:
                slot += 1  # Kodi won't remove the item it is playing; go after it
        self.open(path, slot)
        return slot

    def _sendtokodi(self, open_item, slot, progress, playing, opening):
        """Open a SendToKodi item and, with a watch, wait to see it play."""
        if self.sendtokodi_watch is None:
            open_item()
            return opening
        outcome = self.sendtokodi_watch(self.kodi, open_item, slot=slot)
        if outcome == PLAYING:
            return playing
        if outcome == FAILED:
            raise OmakodiError(say.sendtokodi_failed(self.box), say.SENDTOKODI_FAILED_WHY)
        if outcome == STOPPED:
            return say.stopped(self.box)
        return say.sendtokodi_loading(self.box)

    def play(self, text, progress=None):
        """Play the link now, keeping the queue. Returns the message for the user.

        ``progress(message)`` reports intermediate steps (the fallback).
        """
        t = self.target(text)
        r = t.route
        slot = self.next_slot()
        if progress:  # at once, as the phone remote says it
            progress(say.playing(self.box, how(r)))
        if r is None or not r.youtube_addon:  # SendToKodi
            return self._sendtokodi(lambda: self.open(t.path, slot), slot, progress,
                                    say.playing(self.box, how(r), sure=True), say.playing(self.box, how(r)))
        if not r.fallback or self.verdict is None:
            self.open(t.path, slot)
            return say.playing(self.box, how(r))
        outcome = self.verdict(self.kodi, t, open_item=lambda: self.open(t.path, slot), slot=slot)
        if outcome == PLAYING:
            self.health.clear()
            return say.playing(self.box, sure=True)
        if outcome == UNDECIDED:
            return say.youtube_loading(self.box)
        if outcome == STOPPED:
            return say.stopped(self.box)  # the user's stop: no fallback, nothing for smart mode to learn
        self.health.record_failure()
        if progress:
            progress(say.FALLBACK)
        note = say.FALLBACK_NOTE
        return self._sendtokodi(lambda: self.replace(links.sendtokodi_path(t.url), slot), slot, progress,
                                say.playing(self.box, note, sure=True), say.playing(self.box, note))

    def queue(self, text, progress=None):
        """Add the link to the queue, or play it when nothing is playing."""
        if active_player(self.kodi) is None:
            return self.play(text, progress)
        # A queued video starts later, so there is no fallback; smart mode uses
        # what earlier plays taught it.
        t = self.target(text)
        if self.titles is not None:
            # Before adding it: the daemon reads the queue on Playlist.OnAdd.
            try:
                self.titles.put(t.path, self.title_for(t))
            except OSError:
                pass  # a title is a nicety; queueing goes on
        self.kodi.call("Playlist.Add", {"playlistid": VIDEO_PLAYLIST, "item": {"file": t.path}})
        props = self.kodi.call("Playlist.GetProperties", {"playlistid": VIDEO_PLAYLIST, "properties": ["size"]})
        size = props.get("size") if isinstance(props, dict) else None
        return say.queued(self.box, how(t.route), size)


def make_sender(cfg):
    stops = StopNote()
    mode, _ = youtube_mode(cfg)  # read for each play: a choice in the remote counts at once
    return Sender(Kodi(cfg), mode, YoutubeHealth(host=cfg.host), verdict=Verdict(stops=stops),
                  titles=TitleStore(), youtube_title=youtube_title, sendtokodi_watch=SendToKodiWatch(stops=stops),
                  box=cfg.name)
