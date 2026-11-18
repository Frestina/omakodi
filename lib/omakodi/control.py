"""Remote actions (SPEC "Remote commands")."""

import time

from .audio import MAX_INDEX
from .errors import USAGE, OmakodiError
from .eventserver import SOUNDBAR_ON, run_builtin, send_packet

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
    # Kodi's volume keys: over HDMI-CEC to the TV or soundbar when Kodi
    # passes volume on (SPEC "Volume"); else Kodi's own volume.
    "soundbarup": ("Application.SetVolume", {"volume": "increment"}),
    "soundbardown": ("Application.SetVolume", {"volume": "decrement"}),
    "fullscreen": ("GUI.SetFullscreen", {"fullscreen": "toggle"}),
    # Kodi's player process info on the TV (codecs, resolution, dropped frames).
    "playerinfo": ("Input.ExecuteAction", {"action": "playerprocessinfo"}),
    "powermenu": ("GUI.ActivateWindow", {"window": "shutdownmenu"}),
}

# The box itself, only when Kodi says it may (SPEC "Power"):
# action -> (method, System.GetProperties property, refusal).
SYSTEM = {
    "reboot": ("System.Reboot", "canreboot", "Kodi can't reboot"),
    "shutdown": ("System.Shutdown", "canshutdown", "Kodi can't shut down"),
}

# Kodi builtins JSON-RPC can't run, sent through the EventServer (UDP).
EVENTSERVER = {
    "soundbaron": SOUNDBAR_ON,  # Kodi becomes the active source: the soundbar wakes (CEC)
}

# Kodi's own volume: a number and true/false never go over HDMI-CEC.
KODI_VOLUME = ("volup", "voldown", "mute")
VOLUME_STEP = 5

PLAYER = {
    "playpause": ("Player.PlayPause", {}),
    "stop": ("Player.Stop", {}),
    "next": ("Player.GoTo", {"to": "next"}),
    "previous": ("Player.GoTo", {"to": "previous"}),
    # Kodi's own rewind and fast-forward: each press steps the speed.
    "rewind": ("Player.SetSpeed", {"speed": "decrement"}),
    "fastforward": ("Player.SetSpeed", {"speed": "increment"}),
}

MAX_SEEK = 7 * 24 * 3600  # longer than any video
MAX_VOLUME = 100
VIDEO_PLAYLIST = 1
MAX_QUEUE = 100000

ACTIONS = (tuple(NAVIGATION) + tuple(SIMPLE) + KODI_VOLUME + tuple(PLAYER) + tuple(SYSTEM)
           + tuple(EVENTSERVER))

# During plain fullscreen video these skip a step (10 s) or a big step (up to
# 10 minutes) a press, so a held
# key's repeats are dropped there: a held arrow skips once.
ARROWS = ("up", "down", "left", "right")

FULLSCREEN_CHECK = (
    "Window.IsActive(fullscreenvideo)",
    "Window.IsActive(videoosd)",
    "System.HasActiveModalDialog",
)


def parse_position(text):
    """Seconds from "754", "12:34" or "1:02:03"; None if it isn't one."""
    parts = str(text).strip().split(":")
    if not 1 <= len(parts) <= 3 or not all(p.isdigit() and p.isascii() for p in parts):
        return None
    if any(len(p) > 2 for p in parts[1:]) or any(int(p) > 59 for p in parts[1:]):
        return None
    total = 0
    for p in parts:
        total = total * 60 + int(p)
    return total if total <= MAX_SEEK else None


def _host(kodi):
    host = getattr(getattr(kodi, "cfg", None), "host", "")
    return host if isinstance(host, str) else ""


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

    def __init__(self, kodi, fullscreen_ttl=0.0, clock=time.monotonic, event_send=send_packet, stops=None):
        self.kodi = kodi
        self.stops = stops  # a StopNote: a stop is noted before it goes to Kodi
        self.event_send = event_send
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
        if action in KODI_VOLUME:
            return self._kodi_volume(action)
        if action in PLAYER:
            if action == "stop" and self.stops is not None:
                try:
                    self.stops.record(_host(self.kodi))  # before Kodi stops: a watching play must see it
                except OSError:
                    pass
            player = active_player(self.kodi)
            if player is None:
                raise OmakodiError("nothing playing")
            method, params = PLAYER[action]
            return self.kodi.call(method, {"playerid": player, **params})
        if action in SYSTEM:
            method, prop, refusal = SYSTEM[action]
            allowed = self.kodi.call("System.GetProperties", {"properties": [prop]})
            if not (isinstance(allowed, dict) and allowed.get(prop) is True):
                raise OmakodiError(refusal, f"it says it isn't allowed ({prop} is false)")
            return self.kodi.call(method)
        if action in EVENTSERVER:
            return run_builtin(self.kodi.cfg, EVENTSERVER[action], send=self.event_send)
        raise OmakodiError("unknown action", f"{action!r}; one of: {', '.join(ACTIONS)}", USAGE)

    def _queue_player(self):
        """(player id, playing position) while the video queue plays."""
        player = active_player(self.kodi)
        if player is None:
            raise OmakodiError("nothing playing")
        props = self.kodi.call("Player.GetProperties", {"playerid": player, "properties": ["playlistid", "position"]})
        props = props if isinstance(props, dict) else {}
        if props.get("playlistid") != VIDEO_PLAYLIST or type(props.get("position")) is not int:
            raise OmakodiError("not playing the queue")
        return player, props["position"]

    def _check_position(self, position):
        if type(position) is not int or not 0 <= position < MAX_QUEUE:
            raise OmakodiError("bad position", f"a queue position from 0 to {MAX_QUEUE - 1}", USAGE)
        size = self.kodi.call("Playlist.GetProperties", {"playlistid": VIDEO_PLAYLIST, "properties": ["size"]})
        size = size.get("size") if isinstance(size, dict) else None
        if type(size) is int and position >= size:
            raise OmakodiError("not in the queue", "it changed; look again")

    def goto(self, position):
        """Plays the queue entry at ``position`` (0 is the first)."""
        player, _ = self._queue_player()
        self._check_position(position)
        return self.kodi.call("Player.GoTo", {"playerid": player, "to": position})

    def remove(self, position):
        """Takes the entry at ``position`` out of the queue; not the playing one."""
        _, playing = self._queue_player()
        self._check_position(position)
        if position == playing:
            raise OmakodiError("that one is playing", "stop it or skip it first")
        return self.kodi.call("Playlist.Remove", {"playlistid": VIDEO_PLAYLIST, "position": position})

    def audio(self, index):
        """Plays the audio track with Kodi's ``index``, if the item has it."""
        if type(index) is not int or not 0 <= index <= MAX_INDEX:
            raise OmakodiError("bad audio track", f"an index from 0 to {MAX_INDEX}", USAGE)
        player = active_player(self.kodi)
        if player is None:
            raise OmakodiError("nothing playing")
        props = self.kodi.call("Player.GetProperties", {"playerid": player, "properties": ["audiostreams"]})
        streams = props.get("audiostreams") if isinstance(props, dict) else None
        listed = [s.get("index") for s in streams if isinstance(s, dict)] if isinstance(streams, list) else []
        if not any(type(i) is int and i == index for i in listed):
            raise OmakodiError("no such audio track", "it changed; look again")
        return self.kodi.call("Player.SetAudioStream", {"playerid": player, "stream": index})

    def _kodi_volume(self, action):
        app = self.kodi.call("Application.GetProperties", {"properties": ["volume", "muted"]})
        app = app if isinstance(app, dict) else {}
        if action == "mute":
            return self.kodi.call("Application.SetMute", {"mute": app.get("muted") is not True})
        volume = app.get("volume")
        if type(volume) is not int:
            raise OmakodiError("bad response", "Kodi didn't say its volume")
        step = VOLUME_STEP if action == "volup" else -VOLUME_STEP
        return self.set_volume(max(0, min(MAX_VOLUME, volume + step)))

    def set_volume(self, level):
        """Sets Kodi's own volume (0-100). A number never goes over HDMI-CEC,
        unlike Kodi's volume keys (SPEC "Volume")."""
        if type(level) is not int or not 0 <= level <= MAX_VOLUME:
            raise OmakodiError("bad volume", f"a whole number from 0 to {MAX_VOLUME}", USAGE)
        return self.kodi.call("Application.SetVolume", {"volume": level})

    def seek(self, seconds):
        """Jumps the playing item to ``seconds`` from its start."""
        if type(seconds) is not int or not 0 <= seconds <= MAX_SEEK:
            raise OmakodiError("bad position", f"0 to {MAX_SEEK} seconds", USAGE)
        player = active_player(self.kodi)
        if player is None:
            raise OmakodiError("nothing playing")
        time_ = {"hours": seconds // 3600, "minutes": seconds // 60 % 60, "seconds": seconds % 60,
                 "milliseconds": 0}
        return self.kodi.call("Player.Seek", {"playerid": player, "value": {"time": time_}})
