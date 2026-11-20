"""Reading ~/.config/omakodi/config.json (SPEC "Configuration and credentials")."""

import json
import os
import re
import stat
import tempfile

from .errors import CONFIG, OmakodiError
from .wol import parse_mac

YOUTUBE_MODES = ("smart", "youtube-first", "youtube-only", "sendtokodi-only")
MAX_BYTES = 64 * 1024
# A hostname, IPv4 address or bracket-less IPv6 address. Nothing that could
# change the meaning of the URL it is put into (no "/", "@", "?", "#", spaces).
HOST_RE = re.compile(r"^[A-Za-z0-9._:-]{1,253}$")
# A saved box's id (SPEC "Kodi boxes"): a random UUID when omakodi makes it.
ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def default_path():
    override = os.environ.get("OMAKODI_CONFIG")
    if override:
        return override
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    return os.path.join(base, "omakodi", "config.json")


MAX_BOXES = 32
MAX_NAME = 100
# The keys of one box, in the list form and (all but "name") at the top of
# the single-box form.
BOX_KEYS = ("id", "name", "host", "httpPort", "tcpPort", "eventPort", "username", "password", "mac", "wakeOnLan",
            "youtubeMode")


class Config:
    """The settings omakodi needs for one Kodi box. ``repr`` never shows the password."""

    __slots__ = ("path", "host", "http_port", "tcp_port", "event_port", "username", "password",
                 "youtube_mode", "mac", "wake_on_lan", "name", "id", "saved_id")

    def __init__(self, path, host, http_port=8080, tcp_port=9090, username="", password="",
                 youtube_mode="smart", mac="", wake_on_lan=True, event_port=9777, name="", box_id=""):
        self.path = path
        self.host = host
        # What the box's settings and state are kept under: its id, or its
        # host while the file gives it none (before the move to ids).
        self.id = box_id or host
        self.saved_id = bool(box_id)
        self.http_port = http_port
        self.tcp_port = tcp_port
        self.event_port = event_port
        self.username = username
        self.password = password
        self.youtube_mode = youtube_mode
        # "" or the MAC address that overrides the saved one: valid, or the
        # config's text when it isn't one (waking then says so)
        self.mac = mac
        self.wake_on_lan = wake_on_lan
        self.name = name or host  # what the remote calls the box

    @property
    def mac_ok(self):
        """Whether ``mac`` is a box's MAC address (or empty)."""
        return not self.mac or parse_mac(self.mac) == self.mac

    @property
    def has_login(self):
        return bool(self.username or self.password)

    def public(self):
        """The settings as a dict for display, with the password replaced."""
        return {
            "path": self.path,
            "id": self.id,
            "name": self.name,
            "host": self.host,
            "httpPort": self.http_port,
            "tcpPort": self.tcp_port,
            "eventPort": self.event_port,
            "username": self.username,
            "password": "set" if self.password else "not set",
            "youtubeMode": self.youtube_mode,
            "mac": (self.mac if self.mac_ok else f"{self.mac} (not a MAC address)") if self.mac else "not set",
            "wakeOnLan": self.wake_on_lan,
        }

    def __repr__(self):
        return f"Config(host={self.host!r}, http_port={self.http_port}, tcp_port={self.tcp_port})"


def _bad(detail, path):
    return OmakodiError("bad config", f"{detail} in {path}", CONFIG)


def _port(data, key, default, path, where=""):
    value = data.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 65535:
        raise _bad(f'{where}"{key}" must be a port number (1-65535)', path)
    return value


def _string(data, key, path, where=""):
    value = data.get(key, "")
    if not isinstance(value, str) or len(value) > 1024:
        raise _bad(f'{where}"{key}" must be text', path)
    return value


def _box(data, path, where, default_mode):
    """One box's Config from its JSON object; ``where`` names it in errors."""
    host = data.get("host")
    if not isinstance(host, str) or not HOST_RE.fullmatch(host):
        raise _bad(f'{where}"host" must be a hostname or IP address', path)
    box_id = data.get("id", "")
    if "id" in data and (not isinstance(box_id, str) or not ID_RE.fullmatch(box_id)):
        raise _bad(f'{where}"id" must be letters, digits, "-" or "_" (at most 64)', path)
    name = data.get("name", "")
    if not isinstance(name, str) or len(name) > MAX_NAME or any(ord(c) < 32 or ord(c) == 127 for c in name):
        raise _bad(f'{where}"name" must be one line of text, at most {MAX_NAME} characters', path)
    username = _string(data, "username", path, where)
    password = _string(data, "password", path, where)
    mode = data.get("youtubeMode", default_mode)
    if mode not in YOUTUBE_MODES:
        raise _bad(f'{where}"youtubeMode" must be one of ' + ", ".join(YOUTUBE_MODES), path)
    # A "mac" that isn't a box's MAC address leaves the box working: it is
    # kept as written, and waking says so (SPEC "Wake-on-LAN").
    mac = _string(data, "mac", path, where)
    mac = parse_mac(mac) or mac
    wake_on_lan = data.get("wakeOnLan", True)
    if not isinstance(wake_on_lan, bool):
        raise _bad(f'{where}"wakeOnLan" must be true or false', path)
    return Config(
        path=path,
        host=host,
        http_port=_port(data, "httpPort", 8080, path, where),
        tcp_port=_port(data, "tcpPort", 9090, path, where),
        event_port=_port(data, "eventPort", 9777, path, where),
        username=username,
        password=password,
        youtube_mode=mode,
        mac=mac,
        wake_on_lan=wake_on_lan,
        name=name.strip(),
        box_id=box_id,
    )


def read_file(path=None):
    """The config file as JSON and its stat, checked for size and kind.
    Raises OmakodiError with exit code 3."""
    path = path or default_path()
    try:
        with open(path, "rb") as f:
            st = os.fstat(f.fileno())
            raw = f.read(MAX_BYTES + 1)
    except FileNotFoundError:
        raise OmakodiError("not configured", f"{path} is missing; run `omakodi init`", CONFIG) from None
    except OSError as e:
        raise OmakodiError("bad config", f"can't read {path} ({e.strerror})", CONFIG) from None

    if not stat.S_ISREG(st.st_mode):
        raise _bad("not a regular file", path)
    if len(raw) > MAX_BYTES:
        raise _bad("file is too large", path)
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise _bad("not valid JSON", path) from None
    if not isinstance(data, dict):
        raise _bad("not a JSON object", path)
    return data, st


def parse(data, path, st=None, unique=True):
    """Every box in the config's JSON, in order. Either the single-box form
    (``host`` and the rest at the top) or ``"boxes": [...]``. ``unique``
    refuses two boxes with one id (two without an id on one host)."""
    default_mode = data.get("youtubeMode", "smart")
    if default_mode not in YOUTUBE_MODES:
        raise _bad('"youtubeMode" must be one of ' + ", ".join(YOUTUBE_MODES), path)
    if "boxes" in data:
        if "host" in data:
            raise _bad('give either "host" (one box) or "boxes" (a list), not both', path)
        boxes = data["boxes"]
        if not isinstance(boxes, list) or len(boxes) > MAX_BOXES:
            raise _bad(f'"boxes" must be a list of at most {MAX_BOXES} boxes', path)
        found = []
        for i, box in enumerate(boxes):
            where = f"box {i + 1}: "
            if not isinstance(box, dict):
                raise _bad(f"{where}not a JSON object", path)
            found.append(_box(box, path, where, default_mode))
    else:
        found = [_box(data, path, "", default_mode)]
    seen = set()
    for cfg in found if unique else ():
        # What its state is kept under must be its own (a box without an id
        # goes by its host, in any case).
        keys = {cfg.id} if cfg.saved_id else {cfg.id, cfg.host.lower()}
        if keys & seen:
            if cfg.saved_id:
                raise _bad(f'two boxes have the id "{cfg.id}"', path)
            raise _bad(f'two boxes have the host "{cfg.host}" and no "id"', path)
        seen |= keys

    if st is not None and any(c.password for c in found) and (st.st_uid != os.getuid() or st.st_mode & 0o077):
        if st.st_uid != os.getuid():
            fix = "it must belong to you"
        else:
            fix = f"run `chmod 600 {path}`"
        raise OmakodiError("config readable by others", f"{path} holds a password; {fix}", CONFIG)
    return found


def load_all(path=None):
    """Every box in the config, in order (may be empty). Raises OmakodiError
    with exit code 3."""
    path = path or default_path()
    data, st = read_file(path)
    return parse(data, path, st)


def pick(boxes, chosen, path):
    """The box in use: the one whose id is ``chosen``, else whose host is
    (box.json from before the move to ids), else the first."""
    if not boxes:
        raise OmakodiError("not configured", f"no Kodi box in {path}; add one in the remote", CONFIG)
    for cfg in boxes:
        if cfg.id == chosen:
            return cfg
    for cfg in boxes:
        if cfg.host == chosen:
            return cfg
    return boxes[0]


def load(path=None, chosen=None):
    """The box in use, checked. ``chosen`` is its id; by default the one
    chosen last (in the remote or with `omakodi box`), kept in
    ~/.local/state/omakodi/box.json. Raises OmakodiError with exit code 3."""
    path = path or default_path()
    boxes = load_all(path)
    if chosen is None:
        from .state import chosen_box
        chosen = chosen_box().read()
    return pick(boxes, chosen, path)


def write_file(path, data):
    """Write the config's JSON atomically: a temporary file in its folder
    (mode 600, folder 700), then renamed over it. 2-space indents."""
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, mode=0o700, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=".config.")  # mode 600
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


TEMPLATE = {
    "host": "kodi.example.lan",
    "httpPort": 8080,
    "tcpPort": 9090,
    "username": "kodi",
    "password": "",
    "youtubeMode": "smart",
}


def write_template(path=None):
    """Create a config template with mode 600. Refuses to overwrite."""
    path = path or default_path()
    os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        raise OmakodiError("already configured", f"{path} exists; edit it instead", CONFIG) from None
    with os.fdopen(fd, "w") as f:
        json.dump(TEMPLATE, f, indent=2)
        f.write("\n")
    return path
