"""Remote actions (SPEC "Remote commands")."""

import time

from .errors import USAGE, OmakodiError

# Navigation keys: (normal method, action during plain fullscreen video).
# For select, the fullscreen alternative is a method rather than an action.
NAVIGATION = {
    "up": ("Input.Up", "chapterorbigstepforward"),
    "down": ("Input.Down", "chapterorbigstepback"),
    "left": ("Input.Left", "stepback"),
    "right": ("Input.Right", "stepforward"),
    "select": ("Input.Select", None),
}

SIMPLE = {
    "back": ("Input.Back", None),
    "info": ("Input.Info", None),
    "context": ("Input.ContextMenu", None),
    "osd": ("Input.ShowOSD", None),
    "home": ("GUI.ActivateWindow", {"window": "home"}),
    "volup": ("Application.SetVolume", {"volume": "increment"}),
    "voldown": ("Application.SetVolume", {"volume": "decrement"}),
    "mute": ("Application.SetMute", {"mute": "toggle"}),
    "fullscreen": ("GUI.SetFullscreen", {"fullscreen": "toggle"}),
}

PLAYER = {
    "playpause": "Player.PlayPause",
    "stop": "Player.Stop",
}

ACTIONS = tuple(NAVIGATION) + tuple(SIMPLE) + tuple(PLAYER)

# During plain fullscreen video these skip 10 or 60 s a press, so a held
# key's repeats are dropped there: a held arrow skips once.
ARROWS = ("up", "down", "left", "right")

FULLSCREEN_CHECK = (
    "Window.IsActive(fullscreenvideo)",
    "Window.IsActive(videoosd)",
    "System.HasActiveModalDialog",
)


def active_player(kodi):
    """The id of the active player, preferring video, or None."""
    players = kodi.call("Player.GetActivePlayers")
    if not isinstance(players, list):
        return None
    first = None
    for p in players:
        if not isinstance(p, dict) or not isinstance(p.get("playerid"), int):
            continue
        if p.get("type") == "video":
            return p["playerid"]
        if first is None:
            first = p["playerid"]
    return first


class Controller:
    """Sends remote actions. ``fullscreen_ttl`` caches the fullscreen check,
    so held arrow keys don't double the number of calls (the daemon uses it;
    the one-shot CLI doesn't need it)."""

    def __init__(self, kodi, fullscreen_ttl=0.0, clock=time.monotonic):
        self.kodi = kodi
        self.fullscreen_ttl = fullscreen_ttl
        self.clock = clock
        self._cached = None  # (time, value)

    def plain_fullscreen_video(self, cacheable=True):
        now = self.clock()
        if cacheable and self._cached and now - self._cached[0] < self.fullscreen_ttl:
            return self._cached[1]
        values = self.kodi.call("XBMC.GetInfoBooleans", {"booleans": list(FULLSCREEN_CHECK)})
        values = values if isinstance(values, dict) else {}
        plain = (values.get(FULLSCREEN_CHECK[0]) is True
                 and values.get(FULLSCREEN_CHECK[1]) is not True
                 and values.get(FULLSCREEN_CHECK[2]) is not True)
        self._cached = (now, plain)
        return plain

    def forget(self):
        """Drop the cached fullscreen check (after anything that changes the screen)."""
        self._cached = None

    def run(self, action, repeat=False):
        """Runs ``action``; ``repeat`` marks a held key's repeat. Returns
        Kodi's answer, or None for a repeat dropped during plain fullscreen
        video."""
        if action in NAVIGATION:
            method, video_action = NAVIGATION[action]
            # Select opens the OSD, so its answer must not come from the cache.
            if self.plain_fullscreen_video(cacheable=action != "select"):
                if repeat is True and action in ARROWS:
                    return None
                if action == "select":
                    self.forget()
                    return self.kodi.call("Input.ShowOSD")
                return self.kodi.call("Input.ExecuteAction", {"action": video_action})
            return self.kodi.call(method)
        if action in SIMPLE:
            method, params = SIMPLE[action]
            self.forget()
            return self.kodi.call(method, params)
        if action in PLAYER:
            player = active_player(self.kodi)
            if player is None:
                raise OmakodiError("nothing playing")
            return self.kodi.call(PLAYER[action], {"playerid": player})
        raise OmakodiError("unknown action", f"{action!r}; one of: {', '.join(ACTIONS)}", USAGE)
