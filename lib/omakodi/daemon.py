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
from .control import ACTIONS, MAX_SEEK, Controller
from .errors import AUTH, CONFIG, UNREACHABLE, OmakodiError
from .events import BACKOFF_MAX, BACKOFF_START, ConnectionLost, EventConnection
from .nowplaying import MAX_TEXT, now_playing
from .rpc import Kodi
from .share import make_sender

POLL_ACTIVE = 5.0  # while playing, failing, or without the event port
POLL_IDLE = 60.0  # idle with the event port connected: events tell us
GRACE = 45.0  # continuous failure before Kodi counts as gone
STALE_KEY = 3.0  # a remote key that waited this long in line is skipped
WAIT = 0.25  # longest the monitor blocks before checking its clock again
FULLSCREEN_TTL = 1.0

MAX_LINE = 16 * 1024
MAX_LINK_TEXT = 8 * 1024
MAX_ID_TEXT = 64

# Notifications after which the state is read again.
STATE_EVENTS = ("Player.", "Application.", "System.")
# Remote actions that change the state the shell shows.
STATE_ACTIONS = ("playpause", "stop", "next", "previous", "rewind", "fastforward", "volup", "voldown", "mute")

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
    def __init__(self, load_config, clock=time.monotonic, sender_for=make_sender):
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
        for target, arg in ((self._monitor, None), (self._worker, self._keys), (self._worker, self._links)):
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
        elif cmd == "refresh":
            with self._lock:
                self._refresh_ids.append(rid)
            self._wake.set()
        else:
            self.result(rid, "bad request: unknown command; one of: control, play, queue, refresh, seek, text")

    # ---- commands --------------------------------------------------------------

    def _worker(self, jobs):
        controllers = PerConfig(lambda cfg: Controller(Kodi(cfg), fullscreen_ttl=FULLSCREEN_TTL, clock=self.clock))
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
                    controllers.get(cfg).run(arg, repeat=repeat)
                    message = ""
                elif cmd == "seek":
                    controllers.get(cfg).seek(arg)
                    message = ""
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
            if cmd != "control" or arg in STATE_ACTIONS:
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
            if refresh_ids or poked or self.clock() >= next_poll:
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
                if method == "Input.OnInputRequested":
                    self._set_input(input_request(data))
                elif method == "Input.OnInputFinished":
                    self._set_input(None)
            if any(method.startswith(STATE_EVENTS) for method, _ in events):
                next_poll = self.clock()
        if conn is not None:
            conn.close()

    def _poll(self, kodis, force=False):
        """Read the state, push it if it changed. Returns the config used, or None."""
        now = self.clock()
        cfg = None
        try:
            cfg = self.load_config()
            got = now_playing(kodis.get(cfg))
        except OmakodiError as e:
            self._failing = True
            self._playing = False
            if self._failing_since is None:
                self._failing_since = now
            held = (e.code not in (CONFIG, AUTH) and self._state is not None and self._state["reachable"]
                    and now - self._failing_since < GRACE)
            if not held:
                self._set_state({
                    "reachable": e.code not in (UNREACHABLE, CONFIG),
                    "error": bounded(str(e)),
                    "playing": None, "volume": None, "muted": False,
                }, force)
            elif force:
                self._set_state(self._state, force)
            return cfg
        self._failing = False
        self._failing_since = None
        self._playing = got["playing"] is not None
        self._set_state({"reachable": True, "error": "", **got}, force)
        return cfg

    def _set_input(self, value):
        if value != self._input:
            self._input = value
            if self._state is not None:
                self._set_state(self._state, False)

    def _set_state(self, state, force):
        state = {**state, "input": self._input}
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
