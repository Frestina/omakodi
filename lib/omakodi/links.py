"""Turning text into something Kodi can play (SPEC "Sending a link")."""

import re
import urllib.parse

URL_RE = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
YOUTUBE_HOSTS = {
    "youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com",
    "youtube-nocookie.com", "www.youtube-nocookie.com",
}
PATH_ID_PREFIXES = {"shorts", "live", "embed", "v"}
MAX_URL = 4096

YOUTUBE_ADDON = "plugin.video.youtube"
SENDTOKODI_ADDON = "plugin.video.sendtokodi"


def extract_url(text):
    """The first http(s) link in ``text``, without trailing punctuation, or None."""
    if not isinstance(text, str):
        return None
    m = URL_RE.search(text)
    if not m:
        return None
    url = m.group(0).rstrip(".,;!)")
    if len(url) > MAX_URL:
        return None
    return url


def youtube_video_id(url):
    """The 11-character ID when ``url`` is a single YouTube video, else None."""
    try:
        parts = urllib.parse.urlsplit(url)
    except ValueError:
        return None
    host = (parts.hostname or "").lower()
    segments = [s for s in parts.path.split("/") if s]
    video_id = None
    if host == "youtu.be":
        video_id = segments[0] if segments else None
    elif host in YOUTUBE_HOSTS and segments:
        if segments[0] == "watch":
            values = urllib.parse.parse_qs(parts.query).get("v")
            video_id = values[0] if values else None
        elif segments[0] in PATH_ID_PREFIXES and len(segments) > 1:
            video_id = segments[1]
    if video_id and VIDEO_ID_RE.match(video_id):
        return video_id
    return None


def youtube_path(video_id):
    return f"plugin://{YOUTUBE_ADDON}/play/?video_id={video_id}"


def sendtokodi_path(url):
    return f"plugin://{SENDTOKODI_ADDON}/?url=" + urllib.parse.quote(url, safe="")
