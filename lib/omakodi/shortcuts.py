"""The strip of five shortcut buttons (SPEC "Shortcut buttons").

A button opens one of Kodi's windows, optionally at a path (a library
section, an add-on folder, a source, a playlist), starts an add-on, or is the
remote's own Send a link. The choice is kept per box in
~/.local/state/omakodi/shortcuts.json. Paths and Kodi's art URLs stay in that
file and in the daemon; the state only carries labels, icon names and local
art files.
"""

import json
import os
import re
import tempfile
import threading
import urllib.parse

from .details import plain
from .errors import USAGE, OmakodiError
from .state import state_dir

SLOTS = 5
SEND_LINK = "sendlink"
MAX_LABEL = 150
MAX_PATH = 2048
MAX_ART = 4096
MAX_BOXES = 32
MAX_FILE = 256 * 1024
MAX_ROWS = 500  # rows on one picker page
DIRECTORY_TIMEOUT = 45.0  # Files.GetDirectory runs the add-on on the box

# The built-in icons a button can be given, by name (Panel.qml draws them;
# Shortcuts.js has the same names). Saved by name: never rename one.
ICONS = (
    # video
    "movie", "film", "reel", "clapper", "tv", "tv_classic", "live_tv", "video", "play", "play_box",
    "subscriptions", "camcorder",
    # audio
    "headphones", "music", "music_note", "music_video", "queue_music", "radio", "podcast", "microphone",
    "piano", "guitar",
    # pictures
    "pictures", "image", "camera", "picture_folder",
    # lists
    "playlist", "star", "heart", "bookmark", "thumb_up", "clock", "history", "fire", "trending", "new",
    "explore", "search",
    # topics
    "kids", "smile", "drama", "soccer", "basketball", "racing", "games", "fitness", "news", "world",
    "language", "science", "school", "book", "books", "nature", "pets", "food", "travel", "cars",
    "weather", "ideas",
    # Kodi and the box
    "home", "folder", "drive", "server", "cloud", "cloud_download", "download", "addon", "apps",
    "settings", "info", "link",
)

_WINDOW = re.compile(r"^[a-z0-9_]{1,40}$")
_ADDON_ID = re.compile(r"^[A-Za-z0-9_]+(?:\.[A-Za-z0-9_-]+)+$")
_BARE_PLUGIN = re.compile(r"^plugin://[^/?#]+$", re.I)
_PLUGIN_ID = re.compile(r"^plugin://([^/?#]+)", re.I)
_CONTROL = re.compile(r"[\x00-\x1f\x7f-\x9f]")


# ---- one button ---------------------------------------------------------------

class Shortcut:
    """What one button does. Immutable; compare with ==."""

    __slots__ = ("label", "window", "path", "art", "icon", "action", "typed")

    def __init__(self, label=None, window=None, path=None, art=None, icon=None, action=None, typed=False):
        self.label = label
        self.window = window
        self.path = path
        self.art = art
        self.icon = icon
        self.action = action
        self.typed = typed

    def _key(self):
        return tuple(getattr(self, k) for k in self.__slots__)

    def __eq__(self, other):
        return isinstance(other, Shortcut) and self._key() == other._key()

    def __hash__(self):
        return hash(self._key())

    def __repr__(self):
        return "Shortcut(" + ", ".join(f"{k}={getattr(self, k)!r}" for k in self.__slots__ if getattr(self, k)) + ")"

    def replace(self, **changes):
        values = {k: getattr(self, k) for k in self.__slots__}
        values.update(changes)
        return Shortcut(**values)

    @property
    def send_link(self):
        return self.action == SEND_LINK

    @property
    def launches(self):
        """True for an add-on that is started (a script, a program), not browsed."""
        return self.path is not None and self.window is None and "://" not in self.path

    def resolved_window(self):
        return self.window or (window_for(self.path) if self.path else "home")

    def name(self):
        return self.label or self.path or self.window or "?"

    def encode(self):
        out = {k: getattr(self, k) for k in self.__slots__ if getattr(self, k) not in (None, False)}
        return out

    @classmethod
    def decode(cls, data):
        """A Shortcut from saved JSON, or None when it isn't a valid one."""
        if not isinstance(data, dict):
            return None
        label, window, path, art, icon, action = (data.get(k) for k in
                                                  ("label", "window", "path", "art", "icon", "action"))
        if action is not None:
            if action != SEND_LINK:
                return None
            return cls(label=_label(label) or None, icon=icon if icon in ICONS else None, action=SEND_LINK)
        if window is not None and not (isinstance(window, str) and _WINDOW.match(window)):
            return None
        if path is not None and not valid_path(path):
            return None
        if window is None and path is None:
            return None
        art = art if isinstance(art, str) and 0 < len(art) <= MAX_ART and not _CONTROL.search(art) else None
        return cls(label=_label(label) or None, window=window, path=path, art=art,
                   icon=icon if icon in ICONS else None, typed=data.get("typed") is True)


def _label(value):
    return plain(value, MAX_LABEL) if isinstance(value, str) else ""


DEFAULTS = (
    Shortcut("Home", "home"),
    Shortcut("Movies", "videos", "videodb://movies/titles/"),
    Shortcut("TV shows", "videos", "videodb://tvshows/titles/"),
    Shortcut("Music", "music"),
    Shortcut("Send a link", action=SEND_LINK),
)


# ---- paths --------------------------------------------------------------------

def valid_path(path):
    return isinstance(path, str) and 0 < len(path) <= MAX_PATH and not _CONTROL.search(path)


def normalize(text):
    """A typed Kodi path or add-on id as a button's path; None when it is
    neither. "plugin.video.x" and "plugin://plugin.video.x" both become
    "plugin://plugin.video.x/"; other add-on ids (scripts) stay as they are."""
    t = text.strip() if isinstance(text, str) else ""
    if not t or not valid_path(t):
        return None
    if "://" in t:
        return t + "/" if _BARE_PLUGIN.match(t) else t
    if _ADDON_ID.match(t):
        return f"plugin://{t}/" if t.lower().startswith("plugin.") else t
    return None


def addon_id(path):
    """The add-on behind ``path`` ("plugin.video.youtube"), or None."""
    if not isinstance(path, str):
        return None
    m = _PLUGIN_ID.match(path)
    if m:
        return m.group(1) if _ADDON_ID.match(m.group(1)) else None
    return path if _ADDON_ID.match(path) else None


def window_for(path):
    """The Kodi window a path is browsed in."""
    p = path.lower()
    if p.startswith(("plugin://plugin.audio.", "musicdb://", "library://music")):
        return "music"
    if p.startswith("plugin://plugin.image."):
        return "pictures"
    if p.startswith("plugin://plugin.program."):
        return "programs"
    return "videos"


def open_call(shortcut):
    """(method, params) that opens ``shortcut`` on Kodi."""
    if shortcut.send_link:
        raise OmakodiError("that button sends a link", "the remote opens Send a link for it", USAGE)
    if shortcut.launches:
        return "Addons.ExecuteAddon", {"addonid": shortcut.path}
    if shortcut.path is None:
        return "GUI.ActivateWindow", {"window": shortcut.resolved_window()}
    return "GUI.ActivateWindow", {"window": shortcut.resolved_window(), "parameters": [shortcut.path, "return"]}


def art_url(value):
    """Kodi's art for a button as an ``image://`` URL for ``/image/``, or ""."""
    if not isinstance(value, str) or not value or len(value) > MAX_ART or _CONTROL.search(value):
        return ""
    if value.startswith("image://"):
        return value
    wrapped = "image://" + urllib.parse.quote(value, safe="") + "/"
    return wrapped if len(wrapped) <= MAX_ART else ""


WINDOW_ICONS = {
    "home": "home", "music": "headphones", "videos": "video", "pictures": "pictures",
    "tvchannels": "live_tv", "tvguide": "live_tv", "radiochannels": "radio", "weather": "weather",
    "favouritesbrowser": "star", "addonbrowser": "addon", "programs": "apps", "filemanager": "folder",
    "settings": "settings", "systeminfo": "info",
}


def auto_icon(shortcut):
    """A built-in icon that fits what ``shortcut`` opens."""
    if shortcut.send_link:
        return "link"
    path = (shortcut.path or "").lower()
    if path.endswith(".xsp"):
        return "playlist"
    if addon_id(path):
        return "addon"
    if path.startswith("videodb://musicvideos"):
        return "music_video"
    if path.startswith(("videodb://movies", "videodb://recentlyaddedmovies", "library://video/movies")):
        return "movie"
    if path.startswith(("videodb://tvshows", "videodb://recentlyaddedepisodes", "videodb://inprogresstvshows",
                        "library://video/tvshows")):
        return "tv"
    if path.startswith(("musicdb://", "library://music")):
        return "headphones"
    if path:
        return "folder"
    return WINDOW_ICONS.get(shortcut.resolved_window(), "folder")


# ---- kept per box ---------------------------------------------------------------

class ShortcutStore:
    """The buttons of each box in DIR/shortcuts.json (mode 600):
    ``{"boxes": {"kodi.example.lan": [null, {…}, null, null, null]}}``,
    ``null`` for a button at its default. The most recently changed box is
    last; at most MAX_BOXES are kept."""

    def __init__(self, directory=None):
        self.path = os.path.join(directory or state_dir(), "shortcuts.json")
        self._lock = threading.Lock()
        self._key = None
        self._boxes = {}

    def _stat_key(self):
        try:
            st = os.stat(self.path)
        except OSError:
            return None
        return (st.st_ino, st.st_mtime_ns, st.st_size)

    def _load(self):
        """The saved boxes, read again only when the file changed."""
        key = self._stat_key()
        if key == self._key:
            return self._boxes
        boxes = {}
        try:
            with open(self.path, "rb") as f:
                raw = f.read(MAX_FILE + 1)
            data = json.loads(raw.decode("utf-8")) if len(raw) <= MAX_FILE else None
        except (OSError, UnicodeDecodeError, ValueError):
            data = None
        saved = data.get("boxes") if isinstance(data, dict) else None
        if isinstance(saved, dict):
            for host, slots in list(saved.items())[-MAX_BOXES:]:
                if isinstance(host, str) and isinstance(slots, list) and len(slots) == SLOTS:
                    boxes[host] = [Shortcut.decode(s) if s is not None else None for s in slots]
        self._key, self._boxes = key, boxes
        return boxes

    def custom(self, host):
        """The box's saved buttons: a list of SLOTS Shortcuts or None (default)."""
        with self._lock:
            return list(self._load().get(host) or [None] * SLOTS)

    def buttons(self, host):
        """The box's five buttons as [(shortcut, custom)]."""
        return [(s, True) if s is not None else (DEFAULTS[i], False) for i, s in enumerate(self.custom(host))]

    def set(self, host, slot, shortcut):
        """Keep ``shortcut`` for ``slot`` of ``host``; None or the default resets it."""
        if not 0 <= slot < SLOTS:
            raise ValueError("no such button")
        if shortcut == DEFAULTS[slot]:
            shortcut = None
        with self._lock:
            boxes = dict(self._load())
            slots = list(boxes.pop(host, None) or [None] * SLOTS)
            slots[slot] = shortcut
            if any(s is not None for s in slots):
                boxes[host] = slots  # last: the most recently changed
            boxes = dict(list(boxes.items())[-MAX_BOXES:])
            data = {"boxes": {h: [s.encode() if s is not None else None for s in v] for h, v in boxes.items()}}
            directory = os.path.dirname(self.path)
            os.makedirs(directory, mode=0o700, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=directory, prefix=".shortcuts.json.")
            try:
                with os.fdopen(fd, "w") as f:
                    json.dump(data, f, ensure_ascii=False)
                    f.write("\n")
                os.replace(tmp, self.path)
            except BaseException:
                try:
                    os.remove(tmp)
                except OSError:
                    pass
                raise
            self._key, self._boxes = self._stat_key(), boxes


# ---- the picker -------------------------------------------------------------------

class Page:
    """A page of the "Choose from Kodi" picker."""

    __slots__ = ("kind", "title", "arg", "media", "window", "crumb", "art")

    def __init__(self, kind, title, arg=None, media=None, window=None, crumb=None, art=None):
        self.kind = kind  # root, static, addons, favourites, sources, directory
        self.title = title
        self.arg = arg  # static: its name; addons: the content; directory: the path
        self.media = media
        self.window = window
        self.crumb = crumb or title
        self.art = art

    @property
    def folder(self):
        return self.kind == "directory"

    def as_shortcut(self):
        """The button "Use this folder" makes of a folder page."""
        return Shortcut(self.crumb[:MAX_LABEL], self.window, self.arg, art=self.art or None)


class Item:
    """One row: opens another page (``browse``) or is a button (``choose``)."""

    __slots__ = ("label", "detail", "browse", "choose")

    def __init__(self, label, detail="", browse=None, choose=None):
        self.label = label
        self.detail = detail
        self.browse = browse
        self.choose = choose

    def public(self):
        return {"label": self.label, "detail": self.detail, "browse": self.browse is not None}


def _pick(label, window, path=None):
    return Item(label, choose=Shortcut(label, window, path))


def _folder(label, path, media, window):
    return Item(label, browse=Page("directory", label, path, media, window))


COMMON = (
    _pick("Home", "home"),
    _pick("Movies", "videos", "videodb://movies/titles/"),
    _pick("TV shows", "videos", "videodb://tvshows/titles/"),
    _pick("Music videos", "videos", "videodb://musicvideos/titles/"),
    _pick("Music", "music"),
    _pick("Videos", "videos"),
    _pick("Pictures", "pictures"),
    _pick("Live TV", "tvchannels"),
    _pick("TV guide", "tvguide"),
    _pick("Radio", "radiochannels"),
    _pick("Weather", "weather"),
    _pick("Favourites", "favouritesbrowser"),
    _pick("Add-ons", "addonbrowser"),
    _pick("Programs", "programs"),
    _pick("File manager", "filemanager"),
    _pick("Settings", "settings"),
    _pick("System info", "systeminfo"),
)

VIDEO_LIBRARY = (
    _pick("Movies", "videos", "videodb://movies/titles/"),
    _pick("Recently added movies", "videos", "videodb://recentlyaddedmovies/"),
    _pick("Movie genres", "videos", "videodb://movies/genres/"),
    _pick("Movie sets", "videos", "videodb://movies/sets/"),
    _pick("TV shows", "videos", "videodb://tvshows/titles/"),
    _pick("Recently added episodes", "videos", "videodb://recentlyaddedepisodes/"),
    _pick("In-progress TV shows", "videos", "videodb://inprogresstvshows/"),
    _pick("TV show genres", "videos", "videodb://tvshows/genres/"),
    _pick("Music videos", "videos", "videodb://musicvideos/titles/"),
    _folder("Video playlists", "special://videoplaylists/", "video", "videos"),
    _folder("Library nodes", "library://video/", "video", "videos"),
)

MUSIC_LIBRARY = (
    _pick("Artists", "music", "musicdb://artists/"),
    _pick("Albums", "music", "musicdb://albums/"),
    _pick("Songs", "music", "musicdb://songs/"),
    _pick("Genres", "music", "musicdb://genres/"),
    _pick("Recently added albums", "music", "musicdb://recentlyaddedalbums/"),
    _pick("Recently played albums", "music", "musicdb://recentlyplayedalbums/"),
    _folder("Music playlists", "special://musicplaylists/", "music", "music"),
    _folder("Library nodes", "library://music/", "music", "music"),
)

STATIC = {"common": COMMON, "video": VIDEO_LIBRARY, "music": MUSIC_LIBRARY}

# Add-on content -> (Files.GetDirectory media, window).
ADDON_CONTENT = {"video": ("video", "videos"), "audio": ("music", "music"), "image": ("pictures", "pictures"),
                 "executable": ("programs", "programs")}

ROOT = (
    Item("Common", "Home, Movies, Weather, Settings, …", browse=Page("static", "Common", "common")),
    Item("Video library", browse=Page("static", "Video library", "video")),
    Item("Music library", browse=Page("static", "Music library", "music")),
    Item("Video add-ons", "Open one to pick one of its folders", browse=Page("addons", "Video add-ons", "video")),
    Item("Music add-ons", browse=Page("addons", "Music add-ons", "audio")),
    Item("Picture add-ons", browse=Page("addons", "Picture add-ons", "image")),
    Item("Program add-ons", browse=Page("addons", "Program add-ons", "executable")),
    Item("Favourites", browse=Page("favourites", "Favourites")),
    Item("Video sources", browse=Page("sources", "Video sources", media="video", window="videos")),
    Item("Music sources", browse=Page("sources", "Music sources", media="music", window="music")),
)

ROOT_PAGE = Page("root", "Choose from Kodi")


def _list(result, key):
    rows = result.get(key) if isinstance(result, dict) else None
    return [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else []


def _str(row, key):
    value = row.get(key)
    return value if isinstance(value, str) else ""


def load(kodi, page):
    """The rows of ``page``; raises OmakodiError when Kodi can't list it."""
    if page.kind == "root":
        return list(ROOT)
    if page.kind == "static":
        return list(STATIC.get(page.arg, ()))
    if page.kind == "addons":
        return _addons(kodi, page)
    if page.kind == "favourites":
        return _favourites(kodi)
    if page.kind == "sources":
        return _sources(kodi, page)
    return _directory(kodi, page)


def _directory(kodi, page):
    got = kodi.call("Files.GetDirectory", {"directory": page.arg, "media": page.media,
                                           "properties": ["title", "thumbnail"]},
                    read_timeout=DIRECTORY_TIMEOUT)
    out = []
    for f in _list(got, "files"):
        label = _label(_str(f, "label") or _str(f, "title"))
        path = _str(f, "file")
        if not label or not valid_path(path):
            continue
        art = _str(f, "thumbnail") or page.art  # a folder without art takes its add-on's
        crumb = f"{page.crumb} › {label}"
        if f.get("filetype") == "directory":
            out.append(Item(label, browse=Page("directory", label, path, page.media, page.window, crumb, art)))
        elif path.lower().endswith(".xsp"):
            out.append(Item(label, "Smart playlist", choose=Shortcut(crumb[:MAX_LABEL], page.window, path,
                                                                      art=art or None)))
        # single videos and songs aren't something a button opens
    return out


def _addons(kodi, page):
    media, window = ADDON_CONTENT.get(page.arg, ("video", "videos"))
    got = kodi.call("Addons.GetAddons", {"content": page.arg, "enabled": True,
                                         "properties": ["name", "thumbnail"]})
    out = []
    for a in _list(got, "addons"):
        aid = _str(a, "addonid")
        if not _ADDON_ID.match(aid) or aid.startswith("script.module."):
            continue
        name = _label(_str(a, "name")) or aid
        art = _str(a, "thumbnail") or None
        if aid.startswith("plugin."):
            out.append(Item(name, aid, browse=Page("directory", name, f"plugin://{aid}/", media, window, name, art)))
        else:
            out.append(Item(name, aid, choose=Shortcut(name, None, aid, art=art)))
    out.sort(key=lambda i: i.label.lower())
    return out


def _favourites(kodi):
    got = kodi.call("Favourites.GetFavourites", {"properties": ["window", "windowparameter", "thumbnail"]})
    out = []
    for f in _list(got, "favourites"):
        title = _label(_str(f, "title"))
        window, path = _str(f, "window").lower(), _str(f, "windowparameter")
        if f.get("type") != "window" or not title or not _WINDOW.match(window):
            continue
        out.append(Item(title, choose=Shortcut(title, window, path if valid_path(path) else None,
                                               art=_str(f, "thumbnail") or None)))
    return out


def _sources(kodi, page):
    got = kodi.call("Files.GetSources", {"media": page.media})
    out = []
    for s in _list(got, "sources"):
        label, path = _label(_str(s, "label")), _str(s, "file")
        if label and valid_path(path):
            out.append(Item(label, browse=Page("directory", label, path, page.media, page.window)))
    return out


class Picker:
    """The picker's pages, first page at the bottom. ``seq`` grows with each
    page shown, so a pick from a list that has changed since is refused."""

    def __init__(self):
        self.lock = threading.Lock()
        self.seq = 0
        self.stack = []  # [(page, rows or None, error)]

    def view(self):
        """The page on top, as the ``picker`` line shows it."""
        with self.lock:
            if not self.stack:
                return None
            page, rows, error = self.stack[-1]
            return {
                "seq": self.seq, "title": plain(page.title, 300), "crumb": plain(page.crumb, 300),
                "folder": page.folder, "depth": len(self.stack),
                "status": "failed" if error else ("loading" if rows is None else "ready"),
                "error": error or "",
                "items": [r.public() for r in rows[:MAX_ROWS]] if rows else [],
            }

    def _check(self, seq):
        if seq != self.seq or not self.stack:
            raise OmakodiError("the list changed", "look again")

    def start(self, page=ROOT_PAGE):
        with self.lock:
            self.seq += 1
            self.stack = [(page, None, "")]

    def open(self, seq, index):
        """Opens the row ``index`` of the page with ``seq``: its page goes on top."""
        with self.lock:
            self._check(seq)
            rows = self.stack[-1][1] or []
            if not 0 <= index < len(rows) or rows[index].browse is None:
                raise OmakodiError("the list changed", "look again")
            self.seq += 1
            self.stack.append((rows[index].browse, None, ""))

    def back(self, seq):
        with self.lock:
            self._check(seq)
            if len(self.stack) > 1:
                self.stack.pop()
            self.seq += 1
            page, rows, error = self.stack[-1]
            if error:
                self.stack[-1] = (page, None, "")  # ask again

    def reload(self, seq):
        with self.lock:
            self._check(seq)
            self.seq += 1
            self.stack[-1] = (self.stack[-1][0], None, "")

    def needs_load(self):
        """The page on top when its rows aren't there yet, and its seq."""
        with self.lock:
            if self.stack and self.stack[-1][1] is None and not self.stack[-1][2]:
                return self.stack[-1][0], self.seq
            return None, self.seq

    def loaded(self, seq, rows=None, error=""):
        """The rows (or why not) for the page shown at ``seq``; ignored when
        the picker moved on meanwhile. Returns whether it was kept."""
        with self.lock:
            if seq != self.seq or not self.stack:
                return False
            self.seq += 1
            page = self.stack[-1][0]
            self.stack[-1] = (page, None if error else rows[:MAX_ROWS], error)
            return True

    def chosen(self, seq, index):
        """The button the row ``index`` (or -1: "Use this folder") makes."""
        with self.lock:
            self._check(seq)
            page, rows, _ = self.stack[-1]
            if index == -1:
                if not page.folder:
                    raise OmakodiError("the list changed", "look again")
                return page.as_shortcut()
            rows = rows or []
            if not 0 <= index < len(rows) or rows[index].choose is None:
                raise OmakodiError("the list changed", "look again")
            return rows[index].choose
