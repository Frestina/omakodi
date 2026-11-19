"""What Kodi knows about the playing item, for the remote's Details dialog
(SPEC "Details"). Everything here is plain, bounded text; the item's
``file`` is never asked for, and the cast's photo URLs stay in the daemon."""

import re

from . import art
from .errors import AUTH, UNREACHABLE, OmakodiError

ITEM_PROPERTIES = ["title", "showtitle", "season", "episode", "artist", "plot", "plotoutline", "tagline",
                   "genre", "year", "premiered", "firstaired", "studio", "rating", "votes", "mpaa",
                   "runtime", "director", "writer", "country", "cast", "streamdetails"]
STREAM_PROPERTIES = ["currentvideostream", "currentaudiostream"]
# Add-ons (YouTube, …) may fill Kodi's player labels rather than the item:
# those stand in for every field the item leaves empty.
LABELS = ["VideoPlayer.Plot", "VideoPlayer.Tagline", "VideoPlayer.Artist", "VideoPlayer.Genre",
          "VideoPlayer.Premiered", "VideoPlayer.Year", "VideoPlayer.Studio", "VideoPlayer.Rating",
          "VideoPlayer.Votes", "VideoPlayer.Director", "VideoPlayer.Writer"]

MAX_TITLE = 300
MAX_PLOT = 5000
MAX_INFO = 300
MAX_CAST, MAX_NAME = 20, 60
MAX_BADGES, MAX_BADGE = 5, 20
# The Info rows, in the order they show; each has its own icon in the remote.
INFO_KINDS = ("channel", "genre", "show", "date", "studio", "rating", "age", "runtime",
              "director", "writer", "country")

# Kodi's label formatting. [CR] is a line break; the others only style.
_CR = re.compile(r"\[CR\]", re.I)
_TAGS = re.compile(r"\[(?:/?(?:B|I|LIGHT|UPPERCASE|LOWERCASE|CAPITALIZE|TABS|COLOR)"
                   r"|COLOR[ =]?[^\]\n]{1,40})\]", re.I)
_CONTROL = re.compile(r"[\x00-\x09\x0b-\x1f\x7f-\x9f\ud800-\udfff]")
_YEAR = re.compile(r"^(\d{4})-\d\d-\d\d")


def plain(value, limit, lines=False):
    """``value`` as plain text of at most ``limit`` characters (cut with "…").
    One line, or with ``lines`` its line breaks kept (one empty line at most)."""
    if not isinstance(value, str):
        return ""
    s = _TAGS.sub("", _CR.sub("\n", value))
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = _CONTROL.sub(" ", s)  # "\n" stays
    if lines:
        out = []
        for line in s.split("\n"):
            line = " ".join(line.split())
            if line or (out and out[-1]):
                out.append(line)
        s = "\n".join(out).strip()
    else:
        s = " ".join(s.split())
    if len(s) > limit:
        s = s[:limit - 1].rstrip() + "…"
    return s


def _int(value):
    return value if type(value) is int else 0


def resolution(width, height):
    """Kodi's own steps (StreamDetails' VideoDimsToResolutionDescription)."""
    w, h = _int(width), _int(height)
    if w <= 0 or h <= 0:
        return ""
    if w <= 960 and h <= 576:
        return "SD"
    if w <= 1280 and h <= 962:
        return "720p"
    if w <= 1920 and h <= 1440:
        return "1080p"
    if w <= 4096 and h <= 3072:
        return "4K"
    if w <= 8192 and h <= 6144:
        return "8K"
    return ""


HDR = {"hdr10": "HDR10", "hdr10plus": "HDR10+", "hdr10+": "HDR10+", "dolbyvision": "Dolby Vision",
       "hlg": "HLG"}


def hdr(kind):
    if not isinstance(kind, str) or not kind.strip():
        return ""
    return HDR.get(kind.strip().lower(), "HDR")


def channels(n):
    n = _int(n)
    if n <= 0 or n > 64:
        return ""
    return {1: "Mono", 2: "Stereo", 6: "5.1", 8: "7.1"}.get(n, f"{n} ch")


CODECS = {
    "aac": "AAC", "ac3": "AC3", "eac3": "E-AC3", "eac3_ddp_atmos": "E-AC3 Atmos",
    "dca": "DTS", "dts": "DTS", "dtshd_hra": "DTS-HD HRA", "dtshd_ma": "DTS-HD MA",
    "dtshd_ma_x": "DTS:X", "dtshd_ma_x_imax": "DTS:X IMAX",
    "truehd": "TrueHD", "truehd_atmos": "TrueHD Atmos",
    "flac": "FLAC", "opus": "Opus", "vorbis": "Vorbis", "mp3": "MP3", "mp2": "MP2", "alac": "ALAC",
}


def codec(name):
    if not isinstance(name, str):
        return ""
    key = name.strip().lower()
    if key in CODECS:
        return CODECS[key]
    if key.startswith("pcm"):
        return "PCM"
    return re.sub(r"[^A-Z0-9]", "", key.upper())[:12]


def _first(streams, kind):
    got = streams.get(kind) if isinstance(streams, dict) else None
    got = got[0] if isinstance(got, list) and got else None
    return got if isinstance(got, dict) else {}


VIDEO_CODECS = {"hevc": "HEVC", "h265": "HEVC", "x265": "HEVC", "h264": "H.264", "avc1": "H.264",
                "avc": "H.264", "x264": "H.264", "av1": "AV1", "vp9": "VP9", "vp8": "VP8",
                "mpeg2video": "MPEG-2", "mpeg2": "MPEG-2", "mpeg4": "MPEG-4", "vc1": "VC-1", "wvc1": "VC-1"}


def video_codec(name):
    if not isinstance(name, str):
        return ""
    key = name.strip().lower()
    return VIDEO_CODECS.get(key) or re.sub(r"[^A-Z0-9]", "", key.upper())[:12]


# The badges' words for Dolby's codecs, as a phone remote shows them; the
# others as the audio tracks say them.
BADGE_AUDIO = {"ac3": "DD", "eac3": "DD+", "eac3_ddp_atmos": "DD+ Atmos"}


def audio_badge(name):
    key = name.strip().lower() if isinstance(name, str) else ""
    return BADGE_AUDIO.get(key) or codec(name)


def channels_badge(n):
    """As the audio tracks, but two channels are "2.0" on a badge."""
    return "2.0" if _int(n) == 2 else channels(n)


def badges(live_video, live_audio, streamdetails):
    """Resolution, video codec, HDR, audio codec, audio channels: from what
    plays, else from the library's streamdetails."""
    video = _first(streamdetails, "video")
    audio = _first(streamdetails, "audio")
    live_video = live_video if isinstance(live_video, dict) else {}
    live_audio = live_audio if isinstance(live_audio, dict) else {}
    live_audio_ok = bool(channels(live_audio.get("channels")) or codec(live_audio.get("codec")))
    if not live_audio_ok:
        live_audio = audio
    out = [
        resolution(live_video.get("width"), live_video.get("height"))
        or resolution(video.get("width"), video.get("height")),
        video_codec(live_video.get("codec")) or video_codec(video.get("codec")),
        hdr(live_video.get("hdrtype")) or hdr(video.get("hdrtype")),
        audio_badge(live_audio.get("codec")),
        channels_badge(live_audio.get("channels")),
    ]
    return [b[:MAX_BADGE] for b in out if b][:MAX_BADGES]


def rating(value):
    if type(value) in (int, float) and 0 < value <= 10:
        return f"{value:.1f}"
    return ""


def duration(seconds):
    """1h 2m · 56m · 9m 57s (seconds only under ten minutes)."""
    s = _int(seconds)
    if s <= 0 or s > 7 * 24 * 3600:
        return ""
    m = s // 60
    if m >= 60:
        return f"{m // 60}h {m % 60}m"
    if m >= 10:
        return f"{m}m"
    return f"{m}m {s % 60}s"


def _votes(value):
    digits = value.replace(",", "").replace(".", "").strip() if isinstance(value, str) else (
        str(value) if type(value) is int else "")
    return int(digits) if digits.isdigit() and 0 < int(digits) < 10 ** 12 else 0


# A YouTube description's stats line says "422K Views | 2.68K Likes | 371
# Comments": the views stay, the likes and comments go.
_COUNT = r"[\d.,]+ ?[KMB]? "
_STATS = re.compile(rf"^(?:{_COUNT}views?)?(?:(?:^| \| ){_COUNT}(?:views?|likes?|comments?))+$", re.I)
_LIKES = re.compile(rf"(?:^| \| ){_COUNT}(?:likes?|comments?)", re.I)


def _plot(text):
    lines = plain(text, MAX_PLOT * 2, lines=True).split("\n")
    out = []
    for i, line in enumerate(lines):
        if i < 4 and _STATS.match(line):
            line = _LIKES.sub("", line).strip(" |")
            if not line:
                continue  # only likes and comments: the whole line goes
        out.append(line)
    return "\n".join(out).strip()


class _Fields:
    """An item's fields with the player labels standing in for empty ones."""

    def __init__(self, item, labels):
        self.item, self.labels = item, labels

    def label(self, name):
        return plain(self.labels.get("VideoPlayer." + name), MAX_INFO)

    def list(self, key):
        values = self.item.get(key)
        out = []
        for v in values if isinstance(values, list) else []:
            v = plain(v, MAX_INFO)
            if v and v not in out:
                out.append(v)
        return plain(", ".join(out), MAX_INFO)

    def list_or_label(self, key, name):
        return self.list(key) or plain(self.label(name).replace(" / ", ", "), MAX_INFO)

    def text(self, key, limit=MAX_INFO):
        return plain(self.item.get(key), limit)


def _number(value):
    return value if type(value) is int else -1


def _subtitle(f):
    """"S01E02 · Show", the show, the year, else the channel or artist."""
    item = f.item
    show = f.text("showtitle")
    season, episode = _number(item.get("season")), _number(item.get("episode"))
    if show and season >= 0 and episode >= 0:
        return plain(f"S{season:02d}E{episode:02d} · {show}", MAX_TITLE)
    if show:
        return show
    y = item.get("year")
    if type(y) is int and 1800 <= y <= 2200:
        return str(y)
    return f.list("artist")


def _info(f, played):
    item = f.item
    kind = f.text("type", 20)
    rows = []

    def add(name, text):
        if text:
            rows.append({"kind": name, "text": plain(text, MAX_INFO)})

    if kind != "song":  # for add-on videos the "artist" is the channel
        add("channel", f.list_or_label("artist", "Artist"))
    add("genre", f.list_or_label("genre", "Genre"))
    if kind == "episode":
        add("show", f.text("showtitle"))
    y = item.get("year")
    add("date", f.text("firstaired", 40) or f.text("premiered", 40) or plain(f.label("Premiered"), 40)
        or (str(y) if type(y) is int and 1800 <= y <= 2200 else "") or plain(f.label("Year"), 40))
    add("studio", f.list_or_label("studio", "Studio"))
    score = rating(item.get("rating"))
    if not score:
        try:
            score = rating(float(f.label("Rating")))
        except ValueError:
            score = ""
    if score:
        votes = _votes(item.get("votes")) or _votes(f.label("Votes"))
        add("rating", f"{score} ({votes:,} votes)" if votes else score)
    mpaa = f.text("mpaa")
    add("age", mpaa[6:].strip() if mpaa.lower().startswith("rated ") else mpaa)
    add("runtime", duration(item.get("runtime")) or duration(played))
    add("director", f.list_or_label("director", "Director"))
    add("writer", f.list_or_label("writer", "Writer"))
    add("country", f.list("country"))
    return rows


def _cast(item):
    """Up to 20 of the cast, in Kodi's order, with the ``image://`` URL of
    each one's photo (the daemon fetches it; it never reaches the state)."""
    cast = item.get("cast") if isinstance(item.get("cast"), list) else []
    cast = [c for c in cast if isinstance(c, dict)]
    cast.sort(key=lambda c: c.get("order") if type(c.get("order")) is int else 1 << 30)
    out = []
    for c in cast:
        name = plain(c.get("name"), MAX_NAME)
        if not name:
            continue
        thumb = c.get("thumbnail")
        thumb = thumb if isinstance(thumb, str) and thumb.startswith("image://") and len(thumb) <= art.MAX_URL else ""
        out.append({"name": name, "role": plain(c.get("role"), MAX_NAME), "thumb": thumb})
        if len(out) == MAX_CAST:
            break
    return out


def details(item, live, labels=None, played=0):
    """The details from a Player.GetItem item, the Player.GetProperties
    streams and the player labels (``played``: the playing length, for a
    runtime Kodi doesn't give), or None when there is nothing at all.
    Cast entries carry ``thumb``, their photo's URL, for the daemon only."""
    item = item if isinstance(item, dict) else {}
    live = live if isinstance(live, dict) else {}
    labels = labels if isinstance(labels, dict) else {}
    f = _Fields(item, labels)
    plot = ""
    for raw in (item.get("plot"), labels.get("VideoPlayer.Plot"), item.get("plotoutline"),
                item.get("tagline"), labels.get("VideoPlayer.Tagline")):
        plot = _plot(raw)
        if plot:
            break
    if len(plot) > MAX_PLOT:
        plot = plot[:MAX_PLOT - 1].rstrip() + "…"
    got = {
        "title": f.text("title", MAX_TITLE) or f.text("label", MAX_TITLE),
        "subtitle": _subtitle(f),
        "plot": plot,
        "badges": badges(live.get("currentvideostream"), live.get("currentaudiostream"), item.get("streamdetails")),
        "info": _info(f, played),
        "cast": _cast(item),
    }
    if not (got["plot"] or got["badges"] or got["info"] or got["cast"]):
        return None
    return {k: v for k, v in got.items() if v}


def public(got, photos):
    """``got`` for the state: each cast entry's ``thumb`` swapped for its
    local photo (``photos``: URL -> file), or ``""`` until there is one."""
    if not got:
        return got
    out = dict(got)
    if "cast" in got:
        out["cast"] = [{"name": c["name"], "role": c["role"], "photo": photos.get(c["thumb"], "") if c["thumb"] else ""}
                       for c in got["cast"]]
    return out


def photo_urls(got):
    """The cast photos' URLs of ``got``, in order, each once."""
    out = []
    for c in (got or {}).get("cast", []):
        if c["thumb"] and c["thumb"] not in out:
            out.append(c["thumb"])
    return out


def live_streams_known(live):
    """Whether the player already reported its video or audio stream."""
    live = live if isinstance(live, dict) else {}
    v, a = live.get("currentvideostream"), live.get("currentaudiostream")
    v, a = v if isinstance(v, dict) else {}, a if isinstance(a, dict) else {}
    return bool(resolution(v.get("width"), v.get("height")) or channels(a.get("channels")))


def _ask(kodi, method, params):
    try:
        return kodi.call(method, params)
    except OmakodiError as e:
        if e.code in (UNREACHABLE, AUTH):
            raise
        return None  # an answer we can't use: no details from it


def read_details(kodi, player, played=0):
    """``(details or None, whether the playing streams were known)``."""
    got = _ask(kodi, "Player.GetItem", {"playerid": player, "properties": ITEM_PROPERTIES})
    item = got.get("item") if isinstance(got, dict) else None
    live = _ask(kodi, "Player.GetProperties", {"playerid": player, "properties": STREAM_PROPERTIES})
    labels = _ask(kodi, "XBMC.GetInfoLabels", {"labels": LABELS})
    return details(item, live, labels, played), live_streams_known(live)
