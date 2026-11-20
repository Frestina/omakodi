"""`omakodi daemon`: the shell's live view of Kodi (SPEC "Daemon protocol").

One JSON object per line on stdin (commands) and stdout (state, progress,
results). Three threads besides the reader:

- the monitor follows Kodi's event port and polls the now-playing state,
  pushing it when it changes;
- the key worker runs remote actions in order;
- the link worker runs ``play``/``queue``, which can wait 30 s for the
  YouTube verdict, so a slow play never holds up the arrow keys;
- the browse worker lists Kodi's folders for the shortcut picker, which can
  take 45 s while an add-on runs on the box.

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
from .config import YOUTUBE_MODES
from .art import ArtCache
from . import details as detailsmod
from .details import read_details
from .playqueue import VIDEO_PLAYLIST, read_queue
from .titles import TitleStore
from .audio import MAX_INDEX as MAX_AUDIO_INDEX
from .control import ACTIONS, MAX_QUEUE, MAX_SEEK, MAX_VOLUME, SYSTEM, Controller
from .state import AVOID_SECONDS, ChosenBox, HostValue, StopNote, YoutubeHealth, state_dir
from .youtubemode import mode_store, youtube_mode
from .eventserver import send_packet as event_send
from . import messages
from .errors import AUTH, CONFIG, UNREACHABLE, OmakodiError
from .events import BACKOFF_MAX, BACKOFF_START, ConnectionLost, EventConnection
from .nowplaying import MAX_TEXT, now_playing
from .rpc import Kodi
from . import shortcuts as shortcutsmod
from .shortcuts import ICONS, MAX_ROWS, SLOTS, Picker, ShortcutStore
from .share import make_sender
from . import boxes as boxesmod
from . import boxids
from .wol import MacStore, mac_for, parse_mac, send_packet, wake

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
# The keyboard key ("Type text"): Kodi's keyboard windows, asked for when no
# Input.OnInputRequested was seen (it opened before omakodi listened).
KEYBOARD_WINDOWS = {"Window.IsVisible(virtualkeyboard)": "keyboard", "Window.IsVisible(numericinput)": "number"}
NOT_ASKING = "Kodi isn't asking for text right now"


BROWSE_ACTIONS = ("root", "open", "back", "reload")
BOX_COMMANDS = ("box", "boxSave", "boxDelete", "boxTest", "discover")
SHORTCUT_CHANGES = ("pick", "path", "sendLink", "icon", "reset")
BUTTON_RETRY = 60.0  # an art URL or add-on Kodi couldn't give is asked again after this


def shortcut_change(req):
    """``(slot, how, value)`` from a ``shortcutSet`` request, or why it is bad."""
    slot = req.get("slot")
    if type(slot) is not int or not 0 <= slot < SLOTS:
        return f'"slot" must be a whole number from 0 to {SLOTS - 1}'
    given = [k for k in SHORTCUT_CHANGES if k in req]
    if len(given) != 1:
        return "give exactly one of: " + ", ".join(SHORTCUT_CHANGES)
    how = given[0]
    value = req[how]
    if how == "pick":
        seq = value.get("seq") if isinstance(value, dict) else None
        index = value.get("index") if isinstance(value, dict) else None
        if type(seq) is not int or seq < 0 or type(index) is not int or not -1 <= index < MAX_ROWS:
            return '"pick" must be {"seq": the shown page\'s seq, "index": a row, or -1 for the folder}'
        return slot, how, (seq, index)
    if how == "path":
        if not isinstance(value, str) or len(value) > shortcutsmod.MAX_PATH + 64:
            return '"path" must be text'
        return slot, how, value
    if how == "icon":
        if value != "" and value not in ICONS:
            return '"icon" must be "" or one of the built-in icons'
        return slot, how, value
    if value is not True:
        return f'"{how}" must be true'
    return slot, how, None


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
    """Loads the config's box in use, and again whenever the config file or
    the chosen box (box.json) changes, so fixing it or switching boxes takes
    effect without restarting the shell. Returns the same Config object
    while neither changed. ``boxes()`` is every box and the one in use.
    With ``migrate``, boxes without an id get one (and their state moves to
    it) whenever it reads them (SPEC "Kodi boxes")."""

    def __init__(self, path=None, chosen=None, migrate=None):
        self.path = path or configmod.default_path()
        self.chosen = chosen if chosen is not None else ChosenBox()
        self._migrate = migrate
        self._lock = threading.Lock()
        self._key = None
        self._cfg = None
        self._all = []
        self._error = None

    def _move_to_ids(self):
        """Give the boxes their ids, once per change of the file; when that
        can't be done they go by their host, as before."""
        try:
            self._migrate()
        except Exception as e:  # never stop the daemon for it
            detail = getattr(e, "strerror", None) or type(e).__name__
            print(f"omakodi: can't give the Kodi boxes their ids ({detail})", file=sys.stderr)

    def _stat_key(self):
        try:
            st = os.stat(self.path)
            return (st.st_ino, st.st_mtime_ns, st.st_size, st.st_mode, st.st_uid, self.chosen.stat_key())
        except OSError:
            return None

    def _load(self):
        key = self._stat_key()
        with self._lock:
            if key is None or key != self._key:
                self._key = key
                try:
                    self._all = configmod.load_all(self.path)
                    if self._migrate is not None and any(not b.saved_id for b in self._all):
                        self._move_to_ids()
                        self._key = self._stat_key()
                        self._all = configmod.load_all(self.path)
                    self._cfg = configmod.pick(self._all, self.chosen.read(), self.path)
                    self._error = None
                except OmakodiError as e:
                    if e.kind != "not configured":
                        self._all = []
                    self._cfg, self._error = None, e
            return self._cfg, self._all, self._error

    def __call__(self):
        cfg, _, e = self._load()
        if e is not None:
            raise OmakodiError(e.kind, e.detail, e.code)
        return cfg

    def boxes(self):
        """(every box, the one in use or None); an empty list while the
        config can't be read."""
        cfg, boxes, _ = self._load()
        return boxes, cfg


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
                 macs=None, wake_send=send_packet, event_send=event_send, volume_keys=None, stops=None,
                 youtube_modes=None, health=None, shortcuts=None, book=None, discover=boxesmod.discover,
                 test_box=boxesmod.test_box):
        self.load_config = load_config
        self.clock = clock
        self.sender_for = sender_for
        self._stop = threading.Event()
        self._out = None
        self._out_lock = threading.Lock()
        self._keys = queue.Queue()
        self._links = queue.Queue()
        self._browse = queue.Queue()
        self._manage = queue.Queue()  # Test connection: may wait for a box that isn't there
        self._finder = queue.Queue()  # Found on your network: avahi-browse takes a few seconds
        self._wake = threading.Event()
        self._lock = threading.Lock()
        self._poked = False
        self._refresh_ids = []
        self._threads = []
        # Monitor state
        self._state = None
        self._input = None  # Kodi's on-screen keyboard; the monitor owns it
        self._input_found = None  # one the keyboard key found open, for the monitor to take
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
        # The Details dialog: read on a new item, and once more after the next
        # Player.OnAVStart when the playing streams weren't known yet.
        self._details = None
        self._details_key = None
        self._details_streams = True  # the last read knew the playing streams
        self._details_avstarts = 0
        self._avstarts = 0
        # The cast's photos: the monitor sets the URLs, the art thread fetches
        # them; the state carries only the local files.
        self._cast_wanted = []
        self._cast_photos = {}  # URL -> local file
        # Power (SPEC "Power"): what Kodi allows, and on/off/restarting.
        self._power_caps = None  # {"reboot": bool, "shutdown": bool} once read
        self._power_state = "on"
        self._power_since = 0.0
        # Wake-on-LAN (SPEC "Wake-on-LAN"): the box's MAC address, read
        # while Kodi answers, saved for the config's host.
        self._macs = macs if macs is not None else MacStore()
        self._wake_send = wake_send
        self._event_send = event_send
        self._stops = stops if stops is not None else StopNote()
        # The YouTube mode chosen in the remote's Settings, per box, and the
        # add-on's last failure (smart mode's wait).
        self._youtube_modes = youtube_modes if youtube_modes is not None else mode_store()
        self._health = health if health is not None else YoutubeHealth()
        # Where Kodi's volume keys go (SPEC "Volume"): learnt from Kodi's own
        # volume a second after a key, kept per host.
        self._vk_store = volume_keys if volume_keys is not None else HostValue("volume", "keys", VOLUME_KEYS)
        self._vk_host = None
        self._vk = "unknown"
        self._vol_probe = None  # (action, Kodi's volume before, when)
        self._mac_cfg = None
        self._mac_tries = 0
        # The shortcut buttons (SPEC "Shortcut buttons"): kept per box, their
        # Kodi art fetched by the art thread, the picker on its own worker.
        self._shortcut_store = shortcuts if shortcuts is not None else ShortcutStore()
        self._picker = Picker()
        self._addon_info = {}  # (host, add-on id) -> (name, thumbnail URL)
        self._button_wants = (None, (), ())  # (config, art URLs, add-on ids) the buttons lack
        self._button_tried = {}  # an art URL or add-on id -> when it was last asked for
        self._restate = False  # push the state again without asking Kodi
        # Several boxes (SPEC "Kodi boxes"): the config's list, which one is
        # in use (the monitor follows it), and the boxes found on the network.
        self._book = book
        self._discover = discover
        self._test_box = test_box
        self._box_key = None  # (id, host) of the box the monitor last read
        self._connecting = False  # switched boxes; the new one hasn't answered yet
        self._found = None  # what the last search found, or None before one
        self._found_status = ""  # "searching", "done", "failed"
        self._found_error = ""

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
                            (self._art_worker, None), (self._browser, None), (self._worker, self._manage),
                            (self._worker, self._finder)):
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
        self._browse.put(None)
        self._manage.put(None)
        self._finder.put(None)
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
        elif cmd in ("wake", "keyboard"):
            self._keys.put((rid, cmd, None, self.clock(), False))
        elif cmd == "volume":
            level = req.get("level")
            if type(level) is not int or not 0 <= level <= MAX_VOLUME:
                return self.result(rid, f'bad request: "level" must be a whole number from 0 to {MAX_VOLUME}')
            self._keys.put((rid, cmd, level, self.clock(), False))
        elif cmd == "youtubeMode":
            mode = req.get("mode")
            if mode not in YOUTUBE_MODES:
                return self.result(rid, 'bad request: "mode" must be one of: ' + ", ".join(YOUTUBE_MODES))
            self._keys.put((rid, cmd, mode, self.clock(), False))
        elif cmd == "youtubeRetry":
            self._keys.put((rid, cmd, None, self.clock(), False))
        elif cmd == "shortcut":
            slot = req.get("slot")
            if type(slot) is not int or not 0 <= slot < SLOTS:
                return self.result(rid, f'bad request: "slot" must be a whole number from 0 to {SLOTS - 1}')
            self._keys.put((rid, cmd, slot, self.clock(), False))
        elif cmd == "shortcutSet":
            change = shortcut_change(req)
            if isinstance(change, str):
                return self.result(rid, "bad request: " + change)
            self._keys.put((rid, cmd, change, self.clock(), False))
        elif cmd == "browse":
            action, seq, index = req.get("action"), req.get("seq"), req.get("index")
            if action not in BROWSE_ACTIONS:
                return self.result(rid, 'bad request: "action" must be one of: ' + ", ".join(BROWSE_ACTIONS))
            if action != "root" and (type(seq) is not int or seq < 0):
                return self.result(rid, 'bad request: "seq" must be the shown page\'s seq')
            if action == "open" and (type(index) is not int or not 0 <= index < MAX_ROWS):
                return self.result(rid, f'bad request: "index" must be a whole number from 0 to {MAX_ROWS - 1}')
            self._browse.put((rid, action, seq, index))
        elif cmd in ("box", "boxDelete"):
            # A box by its id, its "key" (a remote older than ids sent its "host").
            box_id = req.get("key", req.get("host"))
            if not isinstance(box_id, str) or not 0 < len(box_id) <= 253:
                return self.result(rid, 'bad request: "key" must be a saved box\'s id')
            self._keys.put((rid, cmd, box_id, self.clock(), False))
        elif cmd in ("boxSave", "boxTest"):
            key, box = req.get("key", ""), req.get("box")
            if not isinstance(key, str) or len(key) > 253:
                return self.result(rid, 'bad request: "key" must be "" or a saved box\'s id')
            if not isinstance(box, dict) or any(k not in boxesmod.EDITOR_FIELDS for k in box):
                return self.result(rid, 'bad request: "box" must be an object with: ' + ", ".join(boxesmod.EDITOR_FIELDS))
            # Saving goes in line with the keys (a switch after it follows it);
            # a test can wait seconds for a box that isn't there.
            (self._keys if cmd == "boxSave" else self._manage).put((rid, cmd, (key, box), self.clock(), False))
        elif cmd == "discover":
            self._finder.put((rid, cmd, None, self.clock(), False))
        elif cmd == "refresh":
            with self._lock:
                self._refresh_ids.append(rid)
            self._wake.set()
        else:
            self.result(rid, "bad request: unknown command; one of: audio, box, boxDelete, boxSave, boxTest, browse, control, "
                             "discover, goto, keyboard, play, queue, refresh, remove, seek, shortcut, shortcutSet, text, "
                             "volume, wake, youtubeMode, youtubeRetry")

    # ---- commands --------------------------------------------------------------

    def _worker(self, jobs):
        controllers = PerConfig(lambda cfg: Controller(Kodi(cfg), fullscreen_ttl=FULLSCREEN_TTL, clock=self.clock,
                                                       event_send=self._event_send, stops=self._stops))
        while True:
            job = jobs.get()
            if job is None or self._stop.is_set():
                return
            rid, cmd, arg, queued_at, repeat = job
            box = None  # the box's name, once its config is read: messages name it
            if cmd == "control" and self.clock() - queued_at > STALE_KEY:
                self.result(rid, "skipped: Kodi was busy with the previous key")
                continue
            try:
                if cmd in BOX_COMMANDS:
                    message = self._box_command(rid, cmd, arg)
                    self.result(rid, message=message)
                    continue
                cfg = self.load_config()
                box = cfg.name
                if cmd == "control":
                    before = self._shown_volume() if arg in ("soundbarup", "soundbardown") else None
                    controllers.get(cfg).run(arg, repeat=repeat)
                    message = messages.soundbar_sent(box) if arg == "soundbaron" else ""
                    if before is not None:
                        with self._lock:
                            self._vol_probe = (arg, before, self.clock())
                elif cmd == "volume":
                    controllers.get(cfg).set_volume(arg)
                    message = ""
                elif cmd == "youtubeMode":
                    try:
                        self._youtube_modes.save(cfg.id, arg)
                    except OSError as e:
                        raise OmakodiError("can't save the YouTube mode", e.strerror or str(e)) from None
                    message = ""
                elif cmd == "youtubeRetry":
                    try:
                        self._health.for_box(cfg.id).clear()
                    except OSError as e:
                        raise OmakodiError("can't forget the YouTube add-on's failure", e.strerror or str(e)) from None
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
                elif cmd == "shortcut":
                    method, params = shortcutsmod.open_call(self._shortcut_store.buttons(cfg.id)[arg][0])
                    controller = controllers.get(cfg)
                    controller.forget()  # the screen changes
                    controller.kodi.call(method, params)
                    message = ""
                elif cmd == "shortcutSet":
                    self._set_shortcut(cfg, *arg)
                    message = ""
                elif cmd == "wake":
                    wake(cfg, self._macs, send=self._wake_send)
                    message = messages.wake_sent(box)
                elif cmd == "keyboard":
                    message = self._find_keyboard(controllers.get(cfg).kodi)
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
                # Test connection's errors name the box being edited, as the
                # phone remote's box screen does (the error carries it).
                said = messages.for_user(e, box) if box is not None or cmd == "boxTest" else str(e)
                self.result(rid, said)
                continue
            except Exception as e:  # a bug must not stop the worker
                traceback.print_exc(file=sys.stderr)
                self.result(rid, f"internal error: {type(e).__name__}")
                continue
            self.result(rid, message=message)
            if cmd == "control" and arg in SYSTEM:
                self._going("off" if arg == "shutdown" else "restarting")
            if cmd == "shortcutSet":
                self.restate()
            elif cmd not in ("control", "wake", "shortcut", "keyboard") or arg in STATE_ACTIONS:
                self.poke()

    # ---- Kodi boxes ----------------------------------------------------------------

    def _need_book(self):
        if self._book is None:
            raise OmakodiError("can't change the boxes here", "this omakodi wasn't started with the config file")
        return self._book

    def _box_command(self, rid, cmd, arg):
        """``box``, ``boxSave``, ``boxDelete``, ``boxTest`` and ``discover``
        (SPEC "Kodi boxes"). Returns the result's message."""
        if cmd == "box":
            cfg = self._need_book().use(arg)
            self.poke()
            return f"Switched to {cfg.name}"
        if cmd == "boxSave":
            key, fields = arg
            cfg = self._need_book().save(key, fields)
            self.poke()
            self._emit_found()  # a found box just added isn't new any more
            return f"Saved {cfg.name}"
        if cmd == "boxDelete":
            self._need_book().delete(arg)
            self.poke()
            self._emit_found()
            return "Deleted"
        if cmd == "boxTest":
            key, fields = arg
            # The saved password only for a saved box, and only while the
            # editor's field is untouched: a found box never gets one.
            password = self._book.password_of(key) if key and self._book is not None else ""
            got = self._test_box(fields, password)
            self.emit({"type": "boxTest", "id": rid, "name": bounded(got["name"], boxesmod.MAX_NAME),
                       "mac": got["mac"]})
            return got["message"]
        # discover
        with self._lock:
            self._found_status, self._found_error = "searching", ""
        self._emit_found()
        try:
            found = self._discover()
        except OmakodiError as e:
            with self._lock:
                self._found_status, self._found_error = "failed", bounded(str(e))
            self._emit_found()
            raise
        with self._lock:
            self._found, self._found_status = found, "done"
        self._emit_found()
        return ""

    def _all_boxes(self):
        """(every box, the one in use or None)."""
        boxes = getattr(self.load_config, "boxes", None)
        if boxes is not None:
            return boxes()
        try:
            cfg = self.load_config()
        except OmakodiError:
            return [], None
        return [cfg], cfg

    def _emit_found(self):
        """The "Found on your network" list: the boxes the last search found
        that aren't saved."""
        with self._lock:
            found, status, error = self._found, self._found_status, self._found_error
        if not status:
            return
        saved, _ = self._all_boxes()
        self.emit({"type": "found", "status": status, "error": error, "total": len(found or []),
                   "boxes": boxesmod.new_boxes(found or [], saved)})

    def _boxes_state(self):
        boxes, current = self._all_boxes()
        return boxesmod.box_list(boxes, current, self._macs)

    def _switched(self, cfg):
        """The monitor reads another box than before: nothing of the last
        box's state stands (SPEC "Kodi boxes")."""
        first = self._box_key is None
        self._box_key = (cfg.id, cfg.host)
        if first:
            return
        with self._lock:
            self._power_state, self._power_since = "on", 0.0
            self._vol_probe = None
            self._art_wanted = self._art_path = ""
        self._failing_since = None
        self._failing = False
        self._playing = False
        self._power_caps = None
        self._queue = self._queue_key = None
        self._details = self._details_key = None
        self._want_cast([])
        self._input = None
        self._connecting = True
        self._set_state({"reachable": False, "error": "", "playing": None, "volume": None, "muted": False,
                         "queue": None, "details": None, "audio": None, "power": None}, True)

    def poke(self):
        """Read the state again soon (a command changed it)."""
        with self._lock:
            self._poked = True
        self._wake.set()

    def restate(self):
        """Push the state again soon, without asking Kodi (omakodi's own part
        of it changed: a button, its art)."""
        with self._lock:
            self._restate = True
        self._wake.set()

    # ---- shortcut buttons --------------------------------------------------------

    def _set_shortcut(self, cfg, slot, how, value):
        """Change a button of the config's box (SPEC "Shortcut buttons")."""
        current = self._shortcut_store.buttons(cfg.id)[slot][0]
        if how == "pick":
            new = self._picker.chosen(*value)
        elif how == "path":
            if value.strip() == "":
                new = None
            else:
                path = shortcutsmod.normalize(value)
                if path is None:
                    raise OmakodiError("not a Kodi path or add-on",
                                       "type one like plugin://plugin.video.youtube or videodb://movies/titles/",
                                       2)
                new = shortcutsmod.Shortcut(path=path, typed=True)
        elif how == "sendLink":
            new = shortcutsmod.DEFAULTS[SLOTS - 1]
        elif how == "icon":
            new = current.replace(icon=value or None)
        else:
            new = None
        try:
            self._shortcut_store.set(cfg.id, slot, new)
        except OSError as e:
            raise OmakodiError("can't save the button", e.strerror or str(e)) from None

    def _browser(self):
        """The picker's worker: one page at a time, Kodi's answers in order."""
        kodis = PerConfig(Kodi)
        while True:
            job = self._browse.get()
            if job is None or self._stop.is_set():
                return
            rid, action, seq, index = job
            try:
                if action == "root":
                    self._picker.start()
                elif action == "open":
                    self._picker.open(seq, index)
                elif action == "back":
                    self._picker.back(seq)
                else:
                    self._picker.reload(seq)
            except OmakodiError as e:
                self._emit_picker()  # what is there now
                self.result(rid, str(e))
                continue
            self._emit_picker()
            page, at = self._picker.needs_load()
            error = ""
            if page is not None:
                rows = None
                try:
                    kodi = kodis.get(self.load_config()) if page.kind not in ("root", "static") else None
                    rows = shortcutsmod.load(kodi, page)
                except OmakodiError as e:
                    error = bounded(str(e))
                except Exception as e:  # a bug must not stop the worker
                    traceback.print_exc(file=sys.stderr)
                    error = f"internal error: {type(e).__name__}"
                if self._picker.loaded(at, rows, error):
                    self._emit_picker()
            self.result(rid, error or None)

    def _emit_picker(self):
        view = self._picker.view()
        if view is not None:
            self.emit({"type": "picker", **view})

    def _shortcuts_state(self):
        """``shortcuts`` for the state: the box's five buttons with their
        labels, icons and local art; asks the art thread for missing art."""
        try:
            cfg = self.load_config()
        except OmakodiError:
            return None
        buttons, urls, addons = [], [], []
        for shortcut, custom in self._shortcut_store.buttons(cfg.id):
            url, name = "", ""
            if not shortcut.send_link:
                url = shortcutsmod.art_url(shortcut.art)
                aid = shortcutsmod.addon_id(shortcut.path)
                if aid is not None:
                    info = self._addon_info.get((cfg.host, aid))
                    if info is None:
                        addons.append(aid)
                    else:
                        name = info[0]
                        url = url or info[1]
            art = self._art_cache.cached(url) if url else ""
            if url and not art:
                urls.append(url)
            buttons.append({
                "label": bounded(shortcut.label or name or shortcut.name(), shortcutsmod.MAX_LABEL),
                "sendLink": shortcut.send_link,
                "icon": shortcut.icon or "",
                "art": art,
                "auto": shortcutsmod.auto_icon(shortcut),
                "custom": custom,
                "typed": bounded(shortcut.path, shortcutsmod.MAX_PATH) if shortcut.typed else "",
            })
        now = self.clock()
        with self._lock:
            self._button_wants = (cfg, tuple(urls), tuple(addons))
            due = any(now - self._button_tried.get(k, -BUTTON_RETRY) >= BUTTON_RETRY for k in urls + addons)
        if due:
            self._art_wake.set()
        return {"box": bounded(cfg.id), "buttons": buttons}

    def _fetch_button_art(self, kodis):
        """Kodi's art for the buttons, and the names and icons of their
        add-ons: each asked for at most once a minute."""
        with self._lock:
            cfg, urls, addons = self._button_wants
        if cfg is None:
            return
        got = False
        try:
            kodi = kodis.get(cfg)
            for aid in addons:
                if not self._button_due(aid):
                    continue
                try:
                    reply = kodi.call("Addons.GetAddonDetails", {"addonid": aid, "properties": ["name", "thumbnail"]})
                except OmakodiError as e:
                    if e.code in (UNREACHABLE, AUTH):
                        raise
                    reply = None  # not installed: no name, no art
                addon = reply.get("addon") if isinstance(reply, dict) else None
                addon = addon if isinstance(addon, dict) else {}
                name, thumb = addon.get("name"), addon.get("thumbnail")
                self._addon_info[(cfg.host, aid)] = (
                    shortcutsmod.plain(name, shortcutsmod.MAX_LABEL) if isinstance(name, str) else "",
                    shortcutsmod.art_url(thumb))
                got = True
            for url in urls:
                if self._button_due(url) and self._art_cache.fetch(kodi, url):
                    got = True
        except OmakodiError:
            pass  # Kodi isn't answering: asked again in a minute
        if got:
            self.restate()

    def _button_due(self, key):
        """Whether ``key`` may be asked for now; notes that it is."""
        now = self.clock()
        with self._lock:
            if now - self._button_tried.get(key, -BUTTON_RETRY) < BUTTON_RETRY:
                return False
            self._button_tried[key] = now
            return True

    # ---- monitor ---------------------------------------------------------------

    def _monitor(self):
        kodis = PerConfig(Kodi)
        conn = conn_cfg = polled_cfg = None
        backoff = BACKOFF_START
        next_connect = self.clock()
        next_poll = self.clock()
        first = True
        while not self._stop.is_set():
            with self._lock:
                refresh_ids, self._refresh_ids = self._refresh_ids, []
                poked, self._poked = self._poked, False
                restate, self._restate = self._restate, False
                found, self._input_found = self._input_found, None
                probe_due = self._vol_probe is not None and self.clock() >= self._vol_probe[2] + VOLUME_PROBE
            if found is not None and self._input is None:
                self._set_input(found)
            try:
                # The config or the chosen box changed (`omakodi box`, an edit):
                # read the box in use now rather than at the next poll.
                changed = self.load_config() is not polled_cfg
            except OmakodiError:
                changed = False
            if refresh_ids or poked or probe_due or changed or self.clock() >= next_poll:
                cfg = self._poll(kodis, force=first or bool(refresh_ids))
                polled_cfg = cfg if cfg is not None else polled_cfg
                first = False
                for rid in refresh_ids:
                    self.result(rid)
                if conn is not None and cfg is not conn_cfg:
                    conn.close()
                    conn = None
                quiet = conn is not None and not self._failing and not self._playing
                next_poll = self.clock() + (POLL_IDLE if quiet else POLL_ACTIVE)
            elif restate and self._state is not None:
                state = self._state
                if state.get("details") and self._details is not None:  # with the cast photos there now
                    with self._lock:
                        state = {**state, "details": detailsmod.public(self._details, self._cast_photos)}
                self._set_state(state, False)

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
        try:  # another box first: the last one's power state (off, restarting) isn't this one's
            chosen = self.load_config()
        except OmakodiError:
            chosen = None
        if chosen is not None and (chosen.id, chosen.host) != self._box_key:
            self._switched(chosen)
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
            got["details"] = self._read_details(kodi, more, (got.get("playing") or {}).get("durationSec", 0))
            got["power"] = self._read_power(kodi)
            self._read_mac(kodi, cfg)
        except OmakodiError as e:
            self._failing = True
            self._playing = False
            self._connecting = False
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
                    # The message, the fix under it (SPEC "Messages"): the top bar shows both.
                    "error": bounded(messages.with_fix(e, cfg.name if cfg is not None else None)),
                    "playing": None, "volume": None, "muted": False, "queue": None, "details": None,
                    "audio": None, "power": None,
                }, force)
            elif force:
                self._set_state(self._state, force)
            return cfg
        self._failing = False
        self._failing_since = None
        self._connecting = False
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
        tries while Kodi says "Busy"), while the box has none yet: one kept
        stays, even after a change of address (SPEC "Wake-on-LAN")."""
        if cfg is not self._mac_cfg:
            self._mac_cfg, self._mac_tries = cfg, 0
        if not cfg.wake_on_lan or cfg.mac or self._mac_tries >= MAC_TRIES:
            return
        if self._macs.read(cfg.id) is not None:
            self._mac_tries = MAC_TRIES
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
            self._macs.save(cfg.id, mac)
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
                    self._vk_store.save(cfg.id, learnt)
                except OSError as e:
                    print(f"omakodi: can't save where the volume keys go ({e.strerror or e})", file=sys.stderr)

    def _volume_keys(self, cfg=None):
        """``volumeKeys`` for the state: what was learnt for this host."""
        if cfg is None:
            try:
                cfg = self.load_config()
            except OmakodiError:
                return "unknown"
        if cfg.id != self._vk_host:
            self._vk_host = cfg.id
            self._vk = self._vk_store.read(cfg.id) or "unknown"
        return self._vk

    def _youtube_state(self):
        """``youtube`` for the state: the mode in use, its source, and smart
        mode's wait after a failure (Unix seconds, 0 when none)."""
        try:
            cfg = self.load_config()
        except OmakodiError:
            return None
        mode, source = youtube_mode(cfg, self._youtube_modes)
        health = self._health.for_box(cfg.id)
        failed = health.failed_at()
        until = round(failed + AVOID_SECONDS) if mode == "smart" and health.failed_recently() else 0
        return {"mode": mode, "from": source, "avoidUntil": until, "box": bounded(cfg.id)}

    def _can_wake(self):
        try:
            cfg = self.load_config()
        except OmakodiError:
            return False
        return mac_for(cfg, self._macs) is not None

    def _wake_on_lan(self):
        """Whether the box may be woken at all (the config's ``wakeOnLan``):
        the remote's power menu offers Wake up unless it is false."""
        try:
            return self.load_config().wake_on_lan
        except OmakodiError:
            return True

    # ---- details ---------------------------------------------------------------

    def _read_details(self, kodi, more, played=0):
        """The state's ``details``: read on a new item only (SPEC "Details")."""
        key = more.get("item")
        if key is None or more.get("player") is None:
            self._details = self._details_key = None
            self._want_cast([])
            return None
        with self._lock:
            avstarts = self._avstarts
        if key != self._details_key or (not self._details_streams and avstarts != self._details_avstarts):
            self._details, self._details_streams = read_details(kodi, more["player"], played)
            self._details_key = key
            self._details_avstarts = avstarts
            self._want_cast(detailsmod.photo_urls(self._details))
        with self._lock:
            return detailsmod.public(self._details, self._cast_photos)

    def _want_cast(self, urls):
        """The cast photos the details show; asks the art thread for the
        ones that aren't here yet."""
        with self._lock:
            if urls == self._cast_wanted:
                return
            self._cast_wanted = urls
            self._cast_photos = {}
            for url in urls:
                path = self._art_cache.cached(url)
                if path:
                    self._cast_photos[url] = path
            missing = len(self._cast_photos) < len(urls)
        if missing:
            self._art_wake.set()

    def _fetch_cast_photos(self, kodis):
        """The cast photos not here yet, in order; the state is pushed again
        after the first six (the cards in view) and at the end."""
        with self._lock:
            urls = [u for u in self._cast_wanted if u not in self._cast_photos]
        if not urls:
            return
        kodi = None
        fresh = 0
        for n, url in enumerate(urls, 1):
            try:
                kodi = kodi or kodis.get(self.load_config())
                path = self._art_cache.fetch(kodi, url)
            except OmakodiError:
                break  # Kodi went away; the next item asks again
            with self._lock:
                if url not in self._cast_wanted:
                    return  # the item changed meanwhile
                if path:
                    self._cast_photos[url] = path
                    fresh += 1
            if fresh and n == 6:
                self._restate_details()
                fresh = 0
        if fresh:
            self._restate_details()

    def _restate_details(self):
        """Push the state again with the cast photos there now."""
        self.restate()

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
            try:
                self._fetch_playing_art(kodis)
                self._fetch_button_art(kodis)  # after what plays: that one shows big
                self._fetch_cast_photos(kodis)  # last: they show only in Details
            except Exception:  # a bug must not stop the thread
                traceback.print_exc(file=sys.stderr)

    def _fetch_playing_art(self, kodis):
        with self._lock:
            url = self._art_wanted
        if not url:
            return
        try:
            path = self._art_cache.fetch(kodis.get(self.load_config()), url)
        except OmakodiError:
            return  # Kodi went away; the next item asks again
        with self._lock:
            if url != self._art_wanted:
                return  # the item changed meanwhile
            self._art_path = path
        if path:
            self.poke()

    def _find_keyboard(self, kodi):
        """The keyboard key: while Kodi's keyboard is open, the remote shows
        its text field. Without an Input.OnInputRequested (it opened before
        omakodi listened), asks Kodi whether one is open. Its text isn't
        read: for a password Kodi would give the password itself. Returns
        the result's message."""
        if self._input is not None:
            return ""
        shown = kodi.call("XBMC.GetInfoBooleans", {"booleans": list(KEYBOARD_WINDOWS)})
        shown = shown if isinstance(shown, dict) else {}
        kind = next((k for w, k in KEYBOARD_WINDOWS.items() if shown.get(w) is True), None)
        if kind is None:
            return NOT_ASKING
        with self._lock:
            self._input_found = {"type": kind, "title": "", "value": ""}
        self.restate()
        return ""

    def _set_input(self, value):
        if value != self._input:
            self._input = value
            if self._state is not None:
                self._set_state(self._state, False)

    def _set_state(self, state, force):
        state = {**state, "wake": self._can_wake(), "wakeOnLan": self._wake_on_lan(), "volumeKeys": self._volume_keys(),
                 "youtube": self._youtube_state(), "shortcuts": self._shortcuts_state(), "input": self._input,
                 "boxes": self._boxes_state(), "connecting": self._connecting}
        if force or state != self._state:
            self._state = state
            self.emit({"type": "state", **state})


def main(path=None):
    """Run on this process's stdin/stdout; never returns."""
    path = path or configmod.default_path()
    chosen = ChosenBox()
    directory = state_dir()
    d = Daemon(ConfigWatcher(path, chosen, migrate=lambda: boxids.migrate(path, directory)),
               book=boxesmod.BoxBook(path, chosen, directory))
    try:
        d.run(sys.stdin.buffer, sys.stdout.buffer)
    except KeyboardInterrupt:
        pass
    d.flush()
    # Workers may sit in a network call; don't wait for them.
    os._exit(0)
