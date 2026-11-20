"""The playing item's audio tracks (SPEC "Audio tracks"): plain, bounded data."""

import re

from . import languages
from .details import plain

PROPERTIES = ["audiostreams", "currentaudiostream"]
MAX_TRACKS = 32
MAX_INDEX = 999
MAX_NAME = 100
MAX_CODEC = 20


def codec(value):
    """Kodi's codec as it says it, in capitals ("eac3" -> "EAC3"), as a phone
    remote shows it; the badges word codecs their own way (details.py)."""
    if not isinstance(value, str):
        return ""
    return re.sub(r"[^A-Z0-9_-]", "", value.strip().upper())[:MAX_CODEC]


def channels(n):
    """2 -> "stereo", 6 -> "5.1"; "" when Kodi doesn't say."""
    if type(n) is not int or n <= 0 or n > 64:
        return ""
    return {1: "mono", 2: "stereo", 6: "5.1", 8: "7.1"}.get(n, f"{n} ch")


def _index(value):
    return value if type(value) is int and 0 <= value <= MAX_INDEX else None


def tracks(props):
    """The state's ``audio`` from Player.GetProperties, or None without tracks."""
    props = props if isinstance(props, dict) else {}
    streams = props.get("audiostreams")
    out, seen = [], set()
    for s in streams if isinstance(streams, list) else []:
        if not isinstance(s, dict):
            continue
        index = _index(s.get("index"))
        if index is None or index in seen:
            continue
        seen.add(index)
        out.append({
            "index": index,
            "name": plain(s.get("name"), MAX_NAME),
            "language": languages.name(s.get("language")),
            "codec": codec(s.get("codec")),
            "channels": channels(s.get("channels")),
        })
        if len(out) == MAX_TRACKS:
            break
    if not out:
        return None
    current = props.get("currentaudiostream")
    current = _index(current.get("index")) if isinstance(current, dict) else None
    return {"current": current if current in seen else -1, "tracks": out}
