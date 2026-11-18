"""Kodi's video queue for the remote (SPEC "The queue")."""

from .errors import AUTH, UNREACHABLE, OmakodiError
from .nowplaying import describe, text

VIDEO_PLAYLIST = 1
WINDOW = 100  # entries in the state at most
BEFORE = 20  # of which before the playing one, when the queue is longer
# Shorter than other titles, so 100 entries stay far below the shell's
# 64 KiB line limit.
MAX_ENTRY_TEXT = 150
ITEM_PROPERTIES = ["title", "showtitle", "season", "episode", "artist", "album"]


def window(position, total):
    """(start, end) of the entries to show: the playing one and those
    around it, at most WINDOW."""
    if total <= WINDOW:
        return 0, total
    start = max(0, min(position - BEFORE, total - WINDOW))
    return start, start + WINDOW


def read_queue(kodi, position, total):
    """The state's ``queue``: the playing position, the window's start, the
    total and the entries' titles. Never asks for an entry's file."""
    start, end = window(position, total)
    items = []
    if end > start:
        try:
            got = kodi.call("Playlist.GetItems", {"playlistid": VIDEO_PLAYLIST, "properties": ITEM_PROPERTIES,
                                                  "limits": {"start": start, "end": end}})
        except OmakodiError as e:
            if e.code in (UNREACHABLE, AUTH):
                raise
            got = None  # an answer we can't use (too large, an error): show no entries
        raw = got.get("items") if isinstance(got, dict) else None
        for item in raw if isinstance(raw, list) else []:
            item = item if isinstance(item, dict) else {}
            title, subtitle = describe(item)
            items.append({"title": (title or text(item.get("label")))[:MAX_ENTRY_TEXT],
                          "subtitle": subtitle[:MAX_ENTRY_TEXT]})
    return {"position": position, "start": start, "total": total, "items": items[:WINDOW]}
