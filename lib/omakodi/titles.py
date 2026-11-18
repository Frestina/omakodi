"""Titles for links queued with omakodi (SPEC "The queue").

Kodi has no title for an add-on item until it plays, and JSON-RPC can't
give it one, so ``queue`` finds one and keeps it here; the daemon's queue
read shows it for entries Kodi has no title for. Keys are a hash of the
queued item's path.
"""

import hashlib
import json
import os
import tempfile
import urllib.error
import urllib.parse
import urllib.request

from .nowplaying import text
from .state import state_dir

MAX_TITLES = 200
MAX_TITLE = 150
MAX_FILE = 64 * 1024
OEMBED = "https://www.youtube.com/oembed"
OEMBED_TIMEOUT = 4.0
MAX_OEMBED = 64 * 1024


def _key(path):
    return hashlib.sha256(str(path).encode("utf-8")).hexdigest()[:32]


def youtube_title(video_id, timeout=OEMBED_TIMEOUT, urlopen=urllib.request.urlopen):
    """The video's title from YouTube's oEmbed endpoint, or "" (any failure)."""
    watch = "https://www.youtube.com/watch?v=" + urllib.parse.quote(video_id, safe="")
    url = OEMBED + "?" + urllib.parse.urlencode({"format": "json", "url": watch})
    req = urllib.request.Request(url, headers={"User-Agent": "omakodi", "Accept": "application/json"})
    try:
        with urlopen(req, timeout=timeout) as resp:
            if getattr(resp, "status", 200) != 200:
                return ""
            raw = resp.read(MAX_OEMBED + 1)
    except (OSError, ValueError, urllib.error.URLError):
        return ""
    if len(raw) > MAX_OEMBED:
        return ""
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return ""
    title = data.get("title") if isinstance(data, dict) else None
    return text(title, MAX_TITLE) if isinstance(title, str) else ""


def link_label(url):
    """'host/path' of a link, for when there is no title."""
    try:
        parts = urllib.parse.urlsplit(url)
    except ValueError:
        return ""
    host = (parts.hostname or "").removeprefix("www.")
    return text(host + parts.path.rstrip("/"), MAX_TITLE)


class TitleStore:
    """Path hash -> title, the MAX_TITLES most recent, in titles.json (600)."""

    def __init__(self, directory=None):
        self.path = os.path.join(directory or state_dir(), "titles.json")
        self._cache_key = None
        self._cache = {}

    def _read(self):
        try:
            st = os.stat(self.path)
        except OSError:
            return {}
        key = (st.st_mtime_ns, st.st_size)
        if key != self._cache_key:
            data = {}
            if st.st_size <= MAX_FILE:
                try:
                    with open(self.path, encoding="utf-8") as f:
                        loaded = json.load(f)
                    if isinstance(loaded, dict):
                        data = {k: v for k, v in loaded.items()
                                if isinstance(k, str) and isinstance(v, str)}
                except (OSError, ValueError):
                    pass
            self._cache_key, self._cache = key, data
        return self._cache

    def version(self):
        """Changes when the file does (another process stored a title)."""
        self._read()
        return self._cache_key

    def get(self, item_path):
        """The stored title for a queued item's path, or ""."""
        return text(self._read().get(_key(item_path), ""), MAX_TITLE) if item_path else ""

    def put(self, item_path, title):
        title = text(title, MAX_TITLE)
        if not item_path or not title:
            return
        data = dict(self._read())
        data.pop(_key(item_path), None)
        data[_key(item_path)] = title  # newest last
        while len(data) > MAX_TITLES:
            data.pop(next(iter(data)))
        directory = os.path.dirname(self.path)
        os.makedirs(directory, mode=0o700, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=directory, prefix=".titles-")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
            os.chmod(tmp, 0o600)
            os.replace(tmp, self.path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
