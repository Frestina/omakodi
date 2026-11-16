"""What Kodi is playing, as plain bounded data for the shell.

The item's ``file`` is never requested: a stream URL from a media-server
add-on can carry an API key.
"""

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


def now_playing(kodi):
    """The state object of SPEC "Daemon protocol", without ``type``/``reachable``."""
    app = kodi.call("Application.GetProperties", {"properties": ["volume", "muted"]})
    app = app if isinstance(app, dict) else {}
    state = {
        "playing": None,
        "volume": app.get("volume") if isinstance(app.get("volume"), int) else None,
        "muted": app.get("muted") is True,
    }
    player = active_player(kodi)
    if player is None:
        return state
    got = kodi.call("Player.GetItem", {"playerid": player, "properties": ITEM_PROPERTIES})
    item = got.get("item") if isinstance(got, dict) else None
    item = item if isinstance(item, dict) else {}
    props = kodi.call("Player.GetProperties", {"playerid": player, "properties": ["time", "totaltime", "speed"]})
    props = props if isinstance(props, dict) else {}
    title, subtitle = describe(item)
    state["playing"] = {
        "title": title,
        "subtitle": subtitle,
        "kind": text(item.get("type"), 20) or "unknown",
        "paused": props.get("speed") == 0,
        "positionSec": seconds(props.get("time")),
        "durationSec": seconds(props.get("totaltime")),
    }
    return state
