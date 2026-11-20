"""What Kodi knows about the playing item, for the remote's Details dialog
(SPEC "Details"). Everything here is plain, bounded text (the plot's bold,
italics and colours go alongside it as ``plotStyles``); the item's
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
MAX_STYLES = 200
# The Info rows, in the order they show; each has its own icon in the remote.
INFO_KINDS = ("channel", "genre", "show", "date", "studio", "rating", "age", "runtime",
              "director", "writer", "country")

# Kodi's label formatting. [CR] is a line break; the others only style.
_CR = re.compile(r"\[CR\]", re.I)
_TAGS = re.compile(r"\[(?:/?(?:B|I|LIGHT|UPPERCASE|LOWERCASE|CAPITALIZE|TABS|COLOR)"
                   r"|COLOR[ =]?[^\]\n]{1,40})\]", re.I)
_CONTROL = re.compile(r"[\x00-\x09\x0b-\x1f\x7f-\x9f\ud800-\udfff]")
# The same tags for the plot, read rather than dropped: 1 "/" or "", 2 the
# name; or 3 COLOR and 4 its colour.
_FORMAT = re.compile(r"\[(/?)(B|I|LIGHT|UPPERCASE|LOWERCASE|CAPITALIZE|TABS|CR|COLOR)\]"
                     r"|\[(COLOR)[ =]?([^\]\n]{1,40})\]", re.I)
_HEX = re.compile(r"(?:[0-9a-f]{2})?([0-9a-f]{6})")
# Kodi's common colour names. The basic ones as light as a phone remote shows
# them on a dark screen; the others as Kodi (and CSS) has them.
COLOURS = {
    "white": "#ffffff", "black": "#000000", "red": "#ff5252", "green": "#69f0ae", "blue": "#82b1ff",
    "yellow": "#ffff8d", "orange": "#ffb74d", "cyan": "#84ffff", "grey": "#b0b0b0", "gray": "#b0b0b0",
    "gold": "#ffd54f", "lime": "#b2ff59", "ghostwhite": "#f8f8ff",
    "silver": "#c0c0c0", "magenta": "#ff00ff", "fuchsia": "#ff00ff", "pink": "#ffc0cb", "purple": "#800080",
    "violet": "#ee82ee", "aqua": "#00ffff", "lightblue": "#add8e6", "skyblue": "#87ceeb",
    "deepskyblue": "#00bfff", "dodgerblue": "#1e90ff", "steelblue": "#4682b4", "navy": "#000080",
    "lightgreen": "#90ee90", "limegreen": "#32cd32", "springgreen": "#00ff7f", "chartreuse": "#7fff00",
    "darkgreen": "#006400", "olive": "#808000", "khaki": "#f0e68c", "lightyellow": "#ffffe0",
    "darkorange": "#ff8c00", "orangered": "#ff4500", "tomato": "#ff6347", "coral": "#ff7f50",
    "salmon": "#fa8072", "crimson": "#dc143c", "darkred": "#8b0000", "maroon": "#800000",
    "brown": "#a52a2a", "tan": "#d2b48c", "beige": "#f5f5dc", "lightgrey": "#d3d3d3",
    "lightgray": "#d3d3d3", "darkgrey": "#a9a9a9", "darkgray": "#a9a9a9", "dimgrey": "#696969",
    "dimgray": "#696969", "teal": "#008080", "turquoise": "#40e0d0", "indigo": "#4b0082",
    "orchid": "#da70d6", "plum": "#dda0dd", "lavender": "#e6e6fa", "whitesmoke": "#f5f5f5",
}
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


def colour(value):
    """The ``#rrggbb`` a ``[COLOR …]`` names: a hex colour (AARRGGBB or
    RRGGBB, with an optional ``#`` or ``0x``; the alpha is ignored) or one of
    ``COLOURS``; ``""`` for anything else."""
    if not isinstance(value, str):
        return ""
    v = value.strip(" =\t").lower()
    if v in COLOURS:
        return COLOURS[v]
    v = v.removeprefix("#").removeprefix("0x")
    m = _HEX.fullmatch(v)
    return "#" + m.group(1) if m else ""


def _styled(raw):
    """``raw``'s characters with Kodi's formatting read: a list of ``(char,
    style)``, style ``(bold, italic, colour)``; ``[CR]`` is a line break, the
    other tags go. A closing tag ends the latest opening one of its kind."""
    out = []
    bold, italic, colours = 0, 0, []
    style = (False, False, "")
    at = 0
    for m in _FORMAT.finditer(raw):
        out.extend((c, style) for c in raw[at:m.start()])
        at = m.end()
        if m.group(3):  # [COLOR x]
            colours.append(colour(m.group(4)))
        else:
            closing, name = m.group(1) == "/", m.group(2).upper()
            if name == "CR":
                if not closing:
                    out.append(("\n", style))
                continue
            if name == "B":
                bold = max(0, bold - 1) if closing else bold + 1
            elif name == "I":
                italic = max(0, italic - 1) if closing else italic + 1
            elif name == "COLOR":
                if not closing:
                    colours.append("")
                elif colours:
                    colours.pop()
            else:
                continue  # LIGHT, UPPERCASE …: no effect
        style = (bold > 0, italic > 0, next((c for c in reversed(colours) if c), ""))
    out.extend((c, style) for c in raw[at:])
    return out


_PLAIN = (False, False, "")


def _styled_lines(raw):
    """The plot's lines as ``_styled`` lists: control characters a space,
    white space runs one space (in the style of the first), no space at
    either end, at most one empty line in a row, none at the ends."""
    raw = raw.replace("\r\n", "\n").replace("\r", "\n")
    lines, line = [], []
    for c, st in _styled(raw):
        if c == "\n":
            lines.append(line)
            line = []
        else:
            line.append((" " if _CONTROL.match(c) else c, st))
    lines.append(line)
    out = []
    for chars in lines:
        kept, space = [], None
        for c, st in chars:
            if c.isspace():
                if kept and space is None:
                    space = (" ", st)
                continue
            if space is not None:
                kept.append(space)
                space = None
            kept.append((c, st))
        if kept or (out and out[-1]):
            out.append(kept)
    while out and not out[-1]:
        out.pop()
    return out


def _utf16(s):
    return len(s.encode("utf-16-le")) // 2


def _spans(chars):
    """``(text, styles)`` from ``(char, style)`` pairs: the ``plotStyles``
    (SPEC "Details"), each a stretch in one style, at most MAX_STYLES."""
    text = "".join(c for c, _ in chars)
    styles = []
    at = 0  # in UTF-16 units
    run = None  # [from, to, style]
    for c, st in chars:
        if c == "\n" and run is not None and run[1] == at:
            st = run[2]  # a line break joins the style it follows
        n = _utf16(c)
        if run is not None and run[2] == st and run[1] == at:
            run[1] += n
        elif st != _PLAIN:
            if run is not None:
                styles.append(run)
            run = [at, at + n, st]
        at += n
    if run is not None:
        styles.append(run)
    out = []
    for start, end, (bold, italic, col) in styles[:MAX_STYLES]:
        span = {"from": start, "to": end}
        if bold:
            span["bold"] = True
        if italic:
            span["italic"] = True
        if col:
            span["color"] = col
        out.append(span)
    return text, out


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
    """Mono, 5.1, 7.1, `N ch`; two channels are "2.0" on a badge."""
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


def _plot(raw):
    """``(plot, plotStyles)``: the plot as plain text, at most MAX_PLOT
    characters, and where Kodi's tags made it bold, italic or coloured."""
    if not isinstance(raw, str):
        return "", []
    out = []
    for i, line in enumerate(_styled_lines(raw[:MAX_PLOT * 8])):
        text = "".join(c for c, _ in line)
        if i < 4 and _STATS.match(text):
            gone = set()
            for m in _LIKES.finditer(text):
                gone.update(range(m.start(), m.end()))
            line = [p for j, p in enumerate(line) if j not in gone]
            while line and line[0][0] in " |":
                line.pop(0)
            while line and line[-1][0] in " |":
                line.pop()
            if not line:
                continue  # only likes and comments: the whole line goes
        if out:
            out.append(("\n", _PLAIN))
        out.extend(line)
    while out and out[0][0].isspace():
        out.pop(0)
    while out and out[-1][0].isspace():
        out.pop()
    if len(out) > MAX_PLOT:
        out = out[:MAX_PLOT - 1]
        while out and out[-1][0].isspace():
            out.pop()
        out.append(("…", _PLAIN))
    return _spans(out)


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
    plot, styles = "", []
    for raw in (item.get("plot"), labels.get("VideoPlayer.Plot"), item.get("plotoutline"),
                item.get("tagline"), labels.get("VideoPlayer.Tagline")):
        plot, styles = _plot(raw)
        if plot:
            break
    got = {
        "title": f.text("title", MAX_TITLE) or f.text("label", MAX_TITLE),
        "subtitle": _subtitle(f),
        "plot": plot,
        "plotStyles": styles if plot else [],
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
