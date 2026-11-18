"""The playing item's audio tracks (SPEC "Audio tracks"): plain, bounded data."""

import re

from .details import channels, codec, plain

PROPERTIES = ["audiostreams", "currentaudiostream"]
MAX_TRACKS = 32
MAX_INDEX = 999
MAX_NAME = 100
MAX_LANGUAGE = 20


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
        language = s.get("language") if isinstance(s.get("language"), str) else ""
        out.append({
            "index": index,
            "name": plain(s.get("name"), MAX_NAME),
            "language": re.sub(r"[^A-Za-z0-9-]", "", language)[:MAX_LANGUAGE],
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
