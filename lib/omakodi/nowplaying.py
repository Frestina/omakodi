"""What Kodi is playing, as plain bounded data for the shell.

The item's ``file`` is never requested: a stream URL from a media-server
add-on can carry an API key.
"""

from . import art
from .control import active_player

MAX_TEXT = 300
ITEM_PROPERTIES = ["title", "showtitle", "season", "episode", "artist", "album"]


def text(value, limit=MAX_TEXT):
    if isinstance(value, list):
        value = ", ".join(str(v) for v in value if isinstance(v, (str, int)))
    if not isinstance(value, (str, int, float)) or isinstance(value, bool):
        return ""
    s = " ".join(str(value).split())  # no newlines or control whitespace
    return s[:limit]


def seconds(t):
    if not isinstance(t, dict):
        return 0
    try:
        return int(t.get("hours", 0)) * 3600 + int(t.get("minutes", 0)) * 60 + int(t.get("seconds", 0))
    except (TypeError, ValueError):
        return 0


def speed(value):
    """Kodi's play speed (1 normal, 0 paused, 2/4/… forward, -2/… rewind)."""
    if type(value) is int and -64 <= value <= 64:
        return value
    return 1


def describe(item):
    """(title, subtitle) for an item from Player.GetItem."""
    title = text(item.get("title")) or text(item.get("label"))
    show = text(item.get("showtitle"))
    season, episode = item.get("season"), item.get("episode")
    if show:
        if isinstance(season, int) and isinstance(episode, int) and season >= 0 and episode >= 0:
            return title, f"{show} · S{season:02d}E{episode:02d}"
        return title, show
    artist, album = text(item.get("artist")), text(item.get("album"))
    return title, " · ".join(x for x in (artist, album) if x)


def now_playing(kodi, extras=False):
    """The state object of SPEC "Daemon protocol", without ``type``/``reachable``.

    ``extras`` also returns what the daemon needs and the state doesn't
    carry: ``(state, {"art": "image://…" or "", "playlistid": int or None,
    "position": int or None})``. The art URL is never put in the state."""
    state, more = _now_playing(kodi, extras)
    return (state, more) if extras else state


def _now_playing(kodi, extras):
    app = kodi.call("Application.GetProperties", {"properties": ["volume", "muted"]})
    app = app if isinstance(app, dict) else {}
    state = {
        "playing": None,
        "volume": app.get("volume") if isinstance(app.get("volume"), int) else None,
        "muted": app.get("muted") is True,
    }
    player = active_player(kodi)
    more = {"art": "", "playlistid": None, "position": None}
    if player is None:
        return state, more
    properties = ITEM_PROPERTIES + (["thumbnail", "art"] if extras else [])
    got = kodi.call("Player.GetItem", {"playerid": player, "properties": properties})
    item = got.get("item") if isinstance(got, dict) else None
    item = item if isinstance(item, dict) else {}
    props = kodi.call("Player.GetProperties", {"playerid": player, "properties": (
        ["time", "totaltime", "speed"] + (["playlistid", "position"] if extras else []))})
    props = props if isinstance(props, dict) else {}
    title, subtitle = describe(item)
    state["playing"] = {
        "title": title,
        "subtitle": subtitle,
        "kind": text(item.get("type"), 20) or "unknown",
        "paused": props.get("speed") == 0,
        "speed": speed(props.get("speed")),
        "positionSec": seconds(props.get("time")),
        "durationSec": seconds(props.get("totaltime")),
    }
    if extras:
        more["art"] = art.source(item)
        for key in ("playlistid", "position"):
            if type(props.get(key)) is int:
                more[key] = props[key]
    return state, more
