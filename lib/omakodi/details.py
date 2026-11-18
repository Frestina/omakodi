"""What Kodi knows about the playing item, for the remote's details card
(SPEC "Details"). Everything here is plain, bounded text; the item's
``file`` is never asked for."""

import re

from .errors import AUTH, UNREACHABLE, OmakodiError

ITEM_PROPERTIES = ["plot", "plotoutline", "genre", "year", "premiered", "firstaired",
                   "studio", "rating", "cast", "streamdetails"]
STREAM_PROPERTIES = ["currentvideostream", "currentaudiostream"]

MAX_PLOT = 3000
MAX_GENRES, MAX_GENRE = 5, 40
MAX_STUDIOS, MAX_STUDIO = 2, 120
MAX_CAST, MAX_NAME = 10, 60
MAX_BADGES, MAX_BADGE = 4, 20

# Kodi's label formatting. [CR] is a line break; the others only style.
_CR = re.compile(r"\[CR\]", re.I)
_TAGS = re.compile(r"\[(?:/?(?:B|I|LIGHT|UPPERCASE|LOWERCASE|CAPITALIZE|TABS|COLOR)"
                   r"|COLOR[ =][^\]\n]{0,40})\]", re.I)
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


def _names(values, count, limit):
    out = []
    for v in values if isinstance(values, list) else []:
        v = plain(v, limit)
        if v and v not in out:
            out.append(v)
        if len(out) == count:
            break
    return out


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


def badges(live_video, live_audio, streamdetails):
    """Resolution, HDR, audio channels, audio codec: from what plays, else
    from the library's streamdetails."""
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
        hdr(video.get("hdrtype")),
        channels(live_audio.get("channels")),
        codec(live_audio.get("codec")),
    ]
    return [b[:MAX_BADGE] for b in out if b][:MAX_BADGES]


def year(item):
    y = item.get("year")
    if type(y) is int and 1800 <= y <= 2200:
        return y
    for key in ("premiered", "firstaired"):
        m = _YEAR.match(item.get(key)) if isinstance(item.get(key), str) else None
        if m and 1800 <= int(m.group(1)) <= 2200:
            return int(m.group(1))
    return 0


def rating(value):
    if type(value) in (int, float) and 0 < value <= 10:
        return f"{value:.1f}"
    return ""


def details(item, live):
    """The state's ``details`` from a Player.GetItem item and the
    Player.GetProperties streams, or None when there is nothing to show."""
    item = item if isinstance(item, dict) else {}
    live = live if isinstance(live, dict) else {}
    cast = item.get("cast") if isinstance(item.get("cast"), list) else []
    studios = _names(item.get("studio"), MAX_STUDIOS, MAX_STUDIO)
    got = {
        "plot": plain(item.get("plot"), MAX_PLOT, lines=True) or plain(item.get("plotoutline"), MAX_PLOT, lines=True),
        "genres": _names(item.get("genre"), MAX_GENRES, MAX_GENRE),
        "year": year(item),
        "studio": plain(", ".join(studios), MAX_STUDIO),
        "rating": rating(item.get("rating")),
        "cast": _names([c.get("name") for c in cast if isinstance(c, dict)], MAX_CAST, MAX_NAME),
        "badges": badges(live.get("currentvideostream"), live.get("currentaudiostream"), item.get("streamdetails")),
    }
    got = {k: v for k, v in got.items() if v}
    return got or None


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


def read_details(kodi, player):
    """``(details or None, whether the playing streams were known)``."""
    got = _ask(kodi, "Player.GetItem", {"playerid": player, "properties": ITEM_PROPERTIES})
    item = got.get("item") if isinstance(got, dict) else None
    live = _ask(kodi, "Player.GetProperties", {"playerid": player, "properties": STREAM_PROPERTIES})
    return details(item, live), live_streams_known(live)
