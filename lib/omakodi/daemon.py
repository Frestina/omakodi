"""`omakodi daemon`: the shell's live view of Kodi (SPEC "Daemon protocol").

One JSON object per line on stdin (commands) and stdout (state, progress,
results). Three threads besides the reader:

- the monitor follows Kodi's event port and polls the now-playing state,
  pushing it when it changes;
- the key worker runs remote actions in order;
- the link worker runs ``play``/``queue``, which can wait 30 s for the
  YouTube verdict, so a slow play never holds up the arrow keys.

Nothing written to stdout contains the password or an item's ``file``:
errors are OmakodiError wordings, and now-playing data never asks for the file.
"""

import json
import os
import queue
import sys
import threading
import time
import traceback

from . import config as configmod
from .art import ArtCache
from .details import read_details
from .playqueue import VIDEO_PLAYLIST, read_queue
from .titles import TitleStore
from .audio import MAX_INDEX as MAX_AUDIO_INDEX
from .control import ACTIONS, MAX_QUEUE, MAX_SEEK, MAX_VOLUME, SYSTEM, Controller
from .state import HostValue
from .eventserver import SOUNDBAR_SENT, send_packet as event_send
from .errors import AUTH, CONFIG, UNREACHABLE, OmakodiError
from .events import BACKOFF_MAX, BACKOFF_START, ConnectionLost, EventConnection
from .nowplaying import MAX_TEXT, now_playing
from .rpc import Kodi
from .share import make_sender
from .wol import SENT as WAKE_SENT, MacStore, mac_for, parse_mac, send_packet, wake

POLL_ACTIVE = 5.0  # while playing, failing, or without the event port
POLL_IDLE = 60.0  # idle with the event port connected: events tell us
GRACE = 45.0  # continuous failure before Kodi counts as gone
STALE_KEY = 3.0  # a remote key that waited this long in line is skipped
WAIT = 0.25  # longest the monitor blocks before checking its clock again
FULLSCREEN_TTL = 1.0
# After a shut down or reboot, Kodi may still answer for a few seconds as it
# closes: answers in this time don't count as it being back.
POWER_QUIET = 15.0
RESTART_WAIT = 180.0  # a reboot with no answer this long: back to "not reachable"
EXIT_POWERDOWN = 64  # System.OnQuit exit code for a shut down
MAC_TRIES = 5  # Kodi says "Busy" while it looks the MAC address up
VOLUME_PROBE = 1.0  # after a volume key, look at Kodi's own volume this much later
VOLUME_KEYS = ("kodi", "tv")  # where the volume keys go, once a key has said

MAX_LINE = 16 * 1024
MAX_LINK_TEXT = 8 * 1024
MAX_ID_TEXT = 64

# Notifications after which the state is read again.
STATE_EVENTS = ("Player.", "Application.", "System.", "Playlist.")
# Remote actions that change the state the shell shows.
STATE_ACTIONS = ("playpause", "stop", "next", "previous", "rewind", "fastforward", "volup", "voldown", "mute",
                 "soundbarup", "soundbardown")

# Kodi's on-screen keyboard (Input.OnInputRequested). The hidden types never
# carry their value; neither does a type this list doesn't know.
INPUT_TYPES = ("keyboard", "password", "numericpassword", "number", "seconds", "time", "date", "ip")
HIDDEN_INPUT = ("password", "numericpassword")


def bounded(s, limit=MAX_TEXT):
    return str(s)[:limit]


def input_request(data):
    """The state's ``input`` for an Input.OnInputRequested ``data`` object."""
    data = data if isinstance(data, dict) else {}
    kind = data.get("type")
    known = kind in INPUT_TYPES
    title, value = data.get("title"), data.get("value")
    return {
        "type": kind if known else "keyboard",
        "title": bounded(title) if isinstance(title, str) else "",
        "value": bounded(value) if known and kind not in HIDDEN_INPUT and isinstance(value, str) else "",
    }


class ConfigWatcher:
    """Loads the config, and again whenever the file changes, so fixing it
    takes effect without restarting the shell. Returns the same Config object
    while the file is unchanged."""

    def __init__(self, path=None):
        self.path = path or configmod.default_path()
        self._lock = threading.Lock()
        self._key = None
        self._cfg = None
        self._error = None

    def __call__(self):
        try:
            st = os.stat(self.path)
            key = (st.st_ino, st.st_mtime_ns, st.st_size, st.st_mode, st.st_uid)
        except OSError:
            key = None
        with self._lock:
            if key is None or key != self._key:
                self._key = key
                try:
                    self._cfg, self._error = configmod.load(self.path), None
                except OmakodiError as e:
                    self._cfg, self._error = None, e
            if self._error is not None:
                e = self._error
                raise OmakodiError(e.kind, e.detail, e.code)
            return self._cfg


class PerConfig:
    """One object (a Kodi client, a Controller) per config, rebuilt when it changes."""

    def __init__(self, build):
        self.build = build
        self.cfg = None
        self.obj = None

    def get(self, cfg):
        if cfg is not self.cfg:
            self.cfg, self.obj = cfg, self.build(cfg)
        return self.obj


class Daemon:
    def __init__(self, load_config, clock=time.monotonic, sender_for=make_sender, art_cache=None, titles=None,
                 macs=None, wake_send=send_packet, event_send=event_send, volume_keys=None):
        self.load_config = load_config
        self.clock = clock
        self.sender_for = sender_for
        self._stop = threading.Event()
        self._out = None
        self._out_lock = threading.Lock()
        self._keys = queue.Queue()
        self._links = queue.Queue()
        self._wake = threading.Event()
        self._lock = threading.Lock()
        self._poked = False
        self._refresh_ids = []
        self._threads = []
        # Monitor state
        self._state = None
        self._input = None  # Kodi's on-screen keyboard; the monitor owns it
        self._failing_since = None
        self._playing = False
        self._failing = False
        # Artwork: the monitor sets what it wants, the art thread fetches it.
        self._art_cache = art_cache if art_cache is not None else ArtCache()
        self._art_wanted = ""  # image:// URL of the playing item, or ""
        self._art_path = ""  # its local file once fetched
        self._art_wake = threading.Event()
        # The queue: read again when its size, the playing position or a
        # Playlist.* event says it changed.
        self._queue = None
        self._queue_key = None
        self._queue_dirty = 0
        self._titles = titles if titles is not None else TitleStore()
        # The details card: read on a new item, and once more after the next
        # Player.OnAVStart when the playing streams weren't known yet.
        self._details = None
        self._details_key = None
        self._details_streams = True  # the last read knew the playing streams
        self._details_avstarts = 0
        self._avstarts = 0
        # Power (SPEC "Power"): what Kodi allows, and on/off/restarting.
        self._power_caps = None  # {"reboot": bool, "shutdown": bool} once read
        self._power_state = "on"
        self._power_since = 0.0
        # Wake-on-LAN (SPEC "Wake-on-LAN"): the box's MAC address, read
        # while Kodi answers, saved for the config's host.
        self._macs = macs if macs is not None else MacStore()
        self._wake_send = wake_send
        self._event_send = event_send
        # Where Kodi's volume keys go (SPEC "Volume"): learnt from Kodi's own
        # volume a second after a key, kept per host.
        self._vk_store = volume_keys if volume_keys is not None else HostValue("volume", "keys", VOLUME_KEYS)
        self._vk_host = None
        self._vk = "unknown"
        self._vol_probe = None  # (action, Kodi's volume before, when)
        self._mac_cfg = None
        self._mac_tries = 0

    # ---- output ----------------------------------------------------------------

    def emit(self, obj):
        line = (json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
        with self._out_lock:
            if self._out is None:
                return
            try:
                self._out.write(line)
                self._out.flush()
            except (OSError, ValueError):
                self._out = None  # the shell went away; stdin closes next
                self._stop.set()

    def result(self, rid, error=None, message=""):
        if error is None:
            self.emit({"type": "result", "id": rid, "ok": True, "message": bounded(message)})
        else:
            self.emit({"type": "result", "id": rid, "ok": False, "error": bounded(error)})

    # ---- lifecycle -------------------------------------------------------------

    def run(self, inp, out):
        """Serve until ``inp`` closes. ``inp``/``out`` are binary files."""
        self._out = out
        for target, arg in ((self._monitor, None), (self._worker, self._keys), (self._worker, self._links),
                            (self._art_worker, None)):
            t = threading.Thread(target=target, args=(arg,) if arg is not None else (), daemon=True)
            t.start()
            self._threads.append(t)
        try:
            while not self._stop.is_set():
                line = inp.readline(MAX_LINE + 1)
                if not line:
                    break
                if len(line) > MAX_LINE and not line.endswith(b"\n"):
                    while True:  # drop the rest of it
                        more = inp.readline(MAX_LINE + 1)
                        if not more or more.endswith(b"\n"):
                            break
                    self.result(None, "bad request: line too long")
                    continue
                self.handle_line(line)
        finally:
            self.stop()

    def stop(self, timeout=0.5):
        self._stop.set()
        self._wake.set()
        self._art_wake.set()
        self._keys.put(None)
        self._links.put(None)
        end = time.monotonic() + timeout
        for t in self._threads:
            t.join(max(0.0, end - time.monotonic()))

    def flush(self, timeout=0.5):
        """Flush stdout, unless a stuck writer holds it."""
        if self._out_lock.acquire(timeout=timeout):
            try:
                if self._out is not None:
                    self._out.flush()
            except (OSError, ValueError):
                pass
            finally:
                self._out_lock.release()

    # ---- input -----------------------------------------------------------------

    def handle_line(self, line):
        if not line.strip():
            return
        try:
            req = json.loads(line.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            return self.result(None, "bad request: not JSON")
        if not isinstance(req, dict):
            return self.result(None, "bad request: not a JSON object")
        rid = req.get("id")
        if not (isinstance(rid, int) and not isinstance(rid, bool) and abs(rid) < 2 ** 53
                or isinstance(rid, str) and len(rid) <= MAX_ID_TEXT):
            return self.result(None, 'bad request: "id" must be a number or short text')
        cmd = req.get("cmd")
        if cmd == "control":
            action = req.get("action")
            if action not in ACTIONS:
                return self.result(rid, "bad request: unknown action; one of: " + ", ".join(ACTIONS))
            self._keys.put((rid, cmd, action, self.clock(), req.get("repeat") is True))
        elif cmd == "text":
            text = req.get("text")
            if not isinstance(text, str) or len(text) > MAX_TEXT:
                return self.result(rid, f'bad request: "text" must be text of up to {MAX_TEXT} characters')
            # In line with the keys, so a typed text never overtakes an arrow.
            self._keys.put((rid, cmd, (text, req.get("done") is True), self.clock(), False))
        elif cmd in ("goto", "remove"):
            position = req.get("position")
            if type(position) is not int or not 0 <= position < MAX_QUEUE:
                return self.result(rid, f'bad request: "position" must be a whole number from 0 to {MAX_QUEUE - 1}')
            self._keys.put((rid, cmd, position, self.clock(), False))
        elif cmd == "audio":
            index = req.get("index")
            if type(index) is not int or not 0 <= index <= MAX_AUDIO_INDEX:
                return self.result(rid, f'bad request: "index" must be a whole number from 0 to {MAX_AUDIO_INDEX}')
            self._keys.put((rid, cmd, index, self.clock(), False))
        elif cmd == "seek":
            seconds = req.get("seconds")
            if type(seconds) is not int or not 0 <= seconds <= MAX_SEEK:
                return self.result(rid, f'bad request: "seconds" must be a whole number from 0 to {MAX_SEEK}')
            self._keys.put((rid, cmd, seconds, self.clock(), False))
        elif cmd in ("play", "queue"):
            text = req.get("text")
            if not isinstance(text, str) or len(text) > MAX_LINK_TEXT:
                return self.result(rid, 'bad request: "text" must be text')
            self._links.put((rid, cmd, text, self.clock(), False))
        elif cmd == "wake":
            self._keys.put((rid, cmd, None, self.clock(), False))
        elif cmd == "volume":
            level = req.get("level")
            if type(level) is not int or not 0 <= level <= MAX_VOLUME:
                return self.result(rid, f'bad request: "level" must be a whole number from 0 to {MAX_VOLUME}')
            self._keys.put((rid, cmd, level, self.clock(), False))
        elif cmd == "refresh":
            with self._lock:
                self._refresh_ids.append(rid)
            self._wake.set()
        else:
            self.result(rid, "bad request: unknown command; one of: audio, control, goto, play, queue, refresh, remove, seek, text, volume, wake")

    # ---- commands --------------------------------------------------------------

    def _worker(self, jobs):
        controllers = PerConfig(lambda cfg: Controller(Kodi(cfg), fullscreen_ttl=FULLSCREEN_TTL, clock=self.clock,
                                                       event_send=self._event_send))
        while True:
            job = jobs.get()
            if job is None or self._stop.is_set():
                return
            rid, cmd, arg, queued_at, repeat = job
            if cmd == "control" and self.clock() - queued_at > STALE_KEY:
                self.result(rid, "skipped: Kodi was busy with the previous key")
                continue
            try:
                cfg = self.load_config()
                if cmd == "control":
                    before = self._shown_volume() if arg in ("soundbarup", "soundbardown") else None
                    controllers.get(cfg).run(arg, repeat=repeat)
                    message = SOUNDBAR_SENT if arg == "soundbaron" else ""
                    if before is not None:
                        with self._lock:
                            self._vol_probe = (arg, before, self.clock())
                elif cmd == "volume":
                    controllers.get(cfg).set_volume(arg)
                    message = ""
                elif cmd == "seek":
                    controllers.get(cfg).seek(arg)
                    message = ""
                elif cmd == "audio":
                    controllers.get(cfg).audio(arg)
                    message = ""
                elif cmd == "goto":
                    controllers.get(cfg).goto(arg)
                    message = ""
                elif cmd == "remove":
                    controllers.get(cfg).remove(arg)
                    message = ""
                elif cmd == "wake":
                    wake(cfg, self._macs, send=self._wake_send)
                    message = WAKE_SENT
                elif cmd == "text":
                    text, done = arg
                    controllers.get(cfg).kodi.call("Input.SendText", {"text": text, "done": done})
                    message = ""
                else:
                    sender = self.sender_for(cfg)
                    send = sender.queue if cmd == "queue" else sender.play
                    message = send(arg, progress=lambda m: self.emit(
                        {"type": "progress", "id": rid, "message": bounded(m)}))
            except OmakodiError as e:
                self.result(rid, str(e))
                continue
            except Exception as e:  # a bug must not stop the worker
                traceback.print_exc(file=sys.stderr)
                self.result(rid, f"internal error: {type(e).__name__}")
                continue
            self.result(rid, message=message)
            if cmd == "control" and arg in SYSTEM:
                self._going("off" if arg == "shutdown" else "restarting")
            if cmd not in ("control", "wake") or arg in STATE_ACTIONS:
                self.poke()

    def poke(self):
        """Read the state again soon (a command changed it)."""
        with self._lock:
            self._poked = True
        self._wake.set()

    # ---- monitor ---------------------------------------------------------------

    def _monitor(self):
        kodis = PerConfig(Kodi)
        conn = conn_cfg = None
        backoff = BACKOFF_START
        next_connect = self.clock()
        next_poll = self.clock()
        first = True
        while not self._stop.is_set():
            with self._lock:
                refresh_ids, self._refresh_ids = self._refresh_ids, []
                poked, self._poked = self._poked, False
                probe_due = self._vol_probe is not None and self.clock() >= self._vol_probe[2] + VOLUME_PROBE
            if refresh_ids or poked or probe_due or self.clock() >= next_poll:
                cfg = self._poll(kodis, force=first or bool(refresh_ids))
                first = False
                for rid in refresh_ids:
                    self.result(rid)
                if conn is not None and cfg is not conn_cfg:
                    conn.close()
                    conn = None
                quiet = conn is not None and not self._failing and not self._playing
                next_poll = self.clock() + (POLL_IDLE if quiet else POLL_ACTIVE)

            # Only knock on the event port while Kodi answers: away from home
            # each attempt would block for the connect timeout.
            if conn is None and not self._failing and self.clock() >= next_connect:
                try:
                    conn_cfg = self.load_config()
                    conn = EventConnection(conn_cfg.host, conn_cfg.tcp_port)
                    conn.open()
                    backoff = BACKOFF_START
                    self._set_input(None)  # a keyboard opened meanwhile went unseen
                except (OmakodiError, ConnectionLost):
                    conn = None
                    next_connect = self.clock() + backoff
                    backoff = min(backoff * 2, BACKOFF_MAX)

            if conn is None:
                self._wake.wait(WAIT)
                self._wake.clear()
                continue
            try:
                events = conn.poll(WAIT)
            except ConnectionLost:
                conn.close()
                conn = None
                next_connect = self.clock() + backoff
                backoff = min(backoff * 2, BACKOFF_MAX)
                next_poll = self.clock()  # Kodi may have gone; find out
                self._set_input(None)
                continue
            for method, data in events:
                if method.startswith("Playlist."):
                    with self._lock:
                        self._queue_dirty += 1
                elif method == "Player.OnAVStart":
                    with self._lock:
                        self._avstarts += 1
                elif method == "System.OnQuit":
                    code = data.get("exitcode") if isinstance(data, dict) else None
                    self._going("off" if code == EXIT_POWERDOWN else "restarting")
                elif method == "System.OnRestart":
                    self._going("restarting")
                if method == "Input.OnInputRequested":
                    self._set_input(input_request(data))
                elif method == "Input.OnInputFinished":
                    self._set_input(None)
            if any(method.startswith(STATE_EVENTS) for method, _ in events):
                next_poll = self.clock()
        if conn is not None:
            conn.close()

    def _going(self, state):
        """Kodi is shutting down ("off") or restarting: say so at once."""
        with self._lock:
            self._power_state = state
            self._power_since = self.clock()
        self.poke()

    def _going_state(self, state):
        return {"reachable": False, "error": "", "playing": None, "volume": None, "muted": False,
                "queue": None, "details": None, "audio": None,
                "power": {"state": state, "reboot": False, "shutdown": False}}

    def _poll(self, kodis, force=False):
        """Read the state, push it if it changed. Returns the config used, or None."""
        now = self.clock()
        cfg = None
        with self._lock:
            if self._power_state == "restarting" and now - self._power_since > RESTART_WAIT:
                self._power_state = "on"  # it didn't come back: plain "not reachable" from here
                self._failing_since = now - GRACE
            going, since = self._power_state, self._power_since
        going = going if going != "on" else None
        if going and now - since < POWER_QUIET:
            self._failing = True
            self._playing = False
            self._set_state(self._going_state(going), force)
            return cfg
        try:
            cfg = self.load_config()
            kodi = kodis.get(cfg)
            got, more = now_playing(kodi, extras=True)
            if going and now - since >= POWER_QUIET:
                with self._lock:
                    self._power_state = "on"  # back: read what it allows again
                self._power_caps = None
                self._mac_tries = 0
            got["queue"] = self._read_queue(kodi, more)
            got["details"] = self._read_details(kodi, more)
            got["power"] = self._read_power(kodi)
            self._read_mac(kodi, cfg)
        except OmakodiError as e:
            self._failing = True
            self._playing = False
            if self._failing_since is None:
                self._failing_since = now
            if going:
                self._set_state(self._going_state(going), force)
                return cfg
            held = (e.code not in (CONFIG, AUTH) and self._state is not None and self._state["reachable"]
                    and now - self._failing_since < GRACE)
            if not held:
                self._set_state({
                    "reachable": e.code not in (UNREACHABLE, CONFIG),
                    "error": bounded(str(e)),
                    "playing": None, "volume": None, "muted": False, "queue": None, "details": None,
                    "audio": None, "power": None,
                }, force)
            elif force:
                self._set_state(self._state, force)
            return cfg
        self._failing = False
        self._failing_since = None
        self._check_volume_keys(cfg, got.get("volume"), now)
        self._playing = got["playing"] is not None
        if got["playing"] is not None:
            got["playing"]["art"] = self._want_art(more["art"])
        self._set_state({"reachable": True, "error": "", **got}, force)
        return cfg

    # ---- the queue -------------------------------------------------------------

    def _read_queue(self, kodi, more):
        """The state's ``queue`` while the video queue plays, else None."""
        position = more.get("position")
        if more.get("playlistid") != VIDEO_PLAYLIST or type(position) is not int or position < 0:
            self._queue = self._queue_key = None
            return None
        props = kodi.call("Playlist.GetProperties", {"playlistid": VIDEO_PLAYLIST, "properties": ["size"]})
        size = props.get("size") if isinstance(props, dict) else None
        if type(size) is not int or size < 0:
            return self._queue
        with self._lock:
            dirty = self._queue_dirty
        key = (position, size, dirty, self._titles.version())
        if key != self._queue_key:
            self._queue = read_queue(kodi, position, size, self._titles)
            self._queue_key = key
        return self._queue

    # ---- power -----------------------------------------------------------------

    def _read_power(self, kodi):
        """``power`` for the state; what Kodi allows is read once per time it's on."""
        if self._power_caps is None:
            try:
                got = kodi.call("System.GetProperties", {"properties": [prop for _, prop, _ in SYSTEM.values()]})
            except OmakodiError as e:
                if e.code in (UNREACHABLE, AUTH):
                    raise
                got = None
            got = got if isinstance(got, dict) else {}
            self._power_caps = {action: got.get(prop) is True for action, (_, prop, _) in SYSTEM.items()}
        return {"state": "on", **self._power_caps}

    def _read_mac(self, kodi, cfg):
        """Save the box's MAC address, read once per time Kodi is on (a few
        tries while Kodi says "Busy")."""
        if cfg is not self._mac_cfg:
            self._mac_cfg, self._mac_tries = cfg, 0
        if not cfg.wake_on_lan or cfg.mac or self._mac_tries >= MAC_TRIES:
            return
        self._mac_tries += 1
        try:
            got = kodi.call("XBMC.GetInfoLabels", {"labels": ["Network.MacAddress"]})
        except OmakodiError as e:
            if e.code in (UNREACHABLE, AUTH):
                raise
            return
        mac = parse_mac(got.get("Network.MacAddress")) if isinstance(got, dict) else None
        if mac is None:
            return
        self._mac_tries = MAC_TRIES
        try:
            self._macs.save(cfg.host, mac)
        except OSError as e:
            print(f"omakodi: can't save the MAC address ({e.strerror or e})", file=sys.stderr)

    # ---- volume ----------------------------------------------------------------

    def _shown_volume(self):
        """Kodi's own volume in the last state, or None."""
        state = self._state
        volume = state.get("volume") if state is not None and state.get("reachable") else None
        return volume if type(volume) is int else None

    def _check_volume_keys(self, cfg, volume, now):
        """After a soundbar key: did Kodi's own volume move (Kodi's volume
        keys go to Kodi) or not, when it could have (over CEC to the TV)?"""
        with self._lock:
            probe = self._vol_probe
        if probe is None or type(volume) is not int:
            return
        action, before, at = probe
        if volume != before:
            learnt = "kodi"
        elif now - at < VOLUME_PROBE:
            return  # Kodi may not have applied it yet
        elif (action == "soundbarup" and before < MAX_VOLUME) or (action == "soundbardown" and before > 0):
            learnt = "tv"
        else:
            learnt = None  # at the limit: nothing to learn
        with self._lock:
            if self._vol_probe == probe:
                self._vol_probe = None
        if learnt is not None:
            self._volume_keys(cfg)
            if learnt != self._vk:
                self._vk = learnt
                try:
                    self._vk_store.save(cfg.host, learnt)
                except OSError as e:
                    print(f"omakodi: can't save where the volume keys go ({e.strerror or e})", file=sys.stderr)

    def _volume_keys(self, cfg=None):
        """``volumeKeys`` for the state: what was learnt for this host."""
        if cfg is None:
            try:
                cfg = self.load_config()
            except OmakodiError:
                return "unknown"
        if cfg.host != self._vk_host:
            self._vk_host = cfg.host
            self._vk = self._vk_store.read(cfg.host) or "unknown"
        return self._vk

    def _can_wake(self):
        try:
            cfg = self.load_config()
        except OmakodiError:
            return False
        return mac_for(cfg, self._macs) is not None

    # ---- details ---------------------------------------------------------------

    def _read_details(self, kodi, more):
        """The state's ``details``: read on a new item only (SPEC "Details")."""
        key = more.get("item")
        if key is None or more.get("player") is None:
            self._details = self._details_key = None
            return None
        with self._lock:
            avstarts = self._avstarts
        if key != self._details_key or (not self._details_streams and avstarts != self._details_avstarts):
            self._details, self._details_streams = read_details(kodi, more["player"])
            self._details_key = key
            self._details_avstarts = avstarts
        return self._details

    # ---- artwork ---------------------------------------------------------------

    def _want_art(self, url):
        """The local art file for ``url`` if there is one yet; asks the art
        thread for it otherwise."""
        with self._lock:
            if url == self._art_wanted:
                return self._art_path
            self._art_wanted = url
            self._art_path = self._art_cache.cached(url) if url else ""
            if url and not self._art_path:
                self._art_wake.set()
            return self._art_path

    def _art_worker(self):
        kodis = PerConfig(Kodi)
        while not self._stop.is_set():
            self._art_wake.wait(WAIT)
            if not self._art_wake.is_set():
                continue
            self._art_wake.clear()
            with self._lock:
                url = self._art_wanted
            if not url:
                continue
            try:
                path = self._art_cache.fetch(kodis.get(self.load_config()), url)
            except OmakodiError:
                continue  # Kodi went away; the next item asks again
            except Exception:  # a bug must not stop the thread
                traceback.print_exc(file=sys.stderr)
                continue
            with self._lock:
                if url != self._art_wanted:
                    continue  # the item changed meanwhile
                self._art_path = path
            if path:
                self.poke()

    def _set_input(self, value):
        if value != self._input:
            self._input = value
            if self._state is not None:
                self._set_state(self._state, False)

    def _set_state(self, state, force):
        state = {**state, "wake": self._can_wake(), "volumeKeys": self._volume_keys(), "input": self._input}
        if force or state != self._state:
            self._state = state
            self.emit({"type": "state", **state})


def main(path=None):
    """Run on this process's stdin/stdout; never returns."""
    d = Daemon(ConfigWatcher(path))
    try:
        d.run(sys.stdin.buffer, sys.stdout.buffer)
    except KeyboardInterrupt:
        pass
    d.flush()
    # Workers may sit in a network call; don't wait for them.
    os._exit(0)
