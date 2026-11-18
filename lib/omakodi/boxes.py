"""Several Kodi boxes (SPEC "Configuration and credentials", "Kodi boxes"):
choosing the one in use, adding, changing and deleting boxes in the config
file, testing a box's settings, and finding boxes on the network.

The config file holds the passwords. It is written only here, atomically
and with mode 600; nothing here puts a password in an error, a message or
the daemon's output.
"""

import json
import os
import re
import shutil
import subprocess
import tempfile
import threading

from . import config as configmod
from .config import BOX_KEYS, MAX_NAME, Config
from .errors import CONFIG, USAGE, OmakodiError
from .rpc import Kodi
from .state import ChosenBox
from .wol import parse_mac

# What Kodi announces over zeroconf: its web server (JSON-RPC over HTTP)
# and its TCP JSON-RPC (the event port).
HTTP_SERVICE = "_xbmc-jsonrpc-h._tcp"
TCP_SERVICE = "_xbmc-jsonrpc._tcp"
SEARCH_TIMEOUT = 10.0
MAX_FOUND = 20
MAX_OUTPUT = 256 * 1024
IPV4_RE = re.compile(r"^(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}$")
# The fields the remote's box editor sends.
EDITOR_FIELDS = ("name", "host", "httpPort", "tcpPort", "username", "password", "mac")
TEST_PATH = "this box's settings"  # where Kodi's errors say to fix it


def one_line(value, limit=MAX_NAME):
    """Plain text on one line: control characters go, spaces are squeezed."""
    if not isinstance(value, str):
        return ""
    text = "".join(" " if ord(c) < 32 or ord(c) == 127 else c for c in value)
    return " ".join(text.split())[:limit]


class BoxBook:
    """The config's boxes and the one in use, for the remote's Manage Kodi
    boxes page and `omakodi box`."""

    def __init__(self, path=None, chosen=None):
        self.path = path or configmod.default_path()
        self.chosen = chosen if chosen is not None else ChosenBox()
        self._lock = threading.Lock()

    # ---- reading ---------------------------------------------------------------

    def boxes(self):
        """Every box (none when there is no config file yet)."""
        try:
            return configmod.load_all(self.path)
        except OmakodiError as e:
            if e.kind == "not configured":
                return []
            raise

    def current(self):
        return configmod.pick(self.boxes(), self.chosen.read(), self.path)

    def find(self, which, boxes=None):
        """The box whose host is ``which``, else whose name is (any case)."""
        boxes = self.boxes() if boxes is None else boxes
        for cfg in boxes:
            if cfg.host == which:
                return cfg
        for cfg in boxes:
            if cfg.name.lower() == str(which).lower():
                return cfg
        names = ", ".join(c.name for c in boxes) or "none yet"
        raise OmakodiError("no such box", f"{which!r} isn't in the config (boxes: {names})", USAGE)

    # ---- changing ----------------------------------------------------------------

    def use(self, which):
        """Make the box named or at ``which`` the one in use. Returns it."""
        cfg = self.find(which)
        try:
            self.chosen.save(cfg.host)
        except OSError as e:
            raise OmakodiError("can't switch boxes", e.strerror or str(e)) from None
        return cfg

    def _read_raw(self):
        """(the top-level keys, the boxes as JSON objects): the single-box
        form becomes a list of one. A file that doesn't parse is left
        alone: it may be half edited."""
        try:
            data, _ = configmod.read_file(self.path)
        except OmakodiError as e:
            if e.kind == "not configured":
                return {}, []
            raise OmakodiError("can't save", f"fix the config file first ({e})", CONFIG) from None
        try:
            if "host" in data or "boxes" in data:
                configmod.parse(data, self.path)
        except OmakodiError as e:
            raise OmakodiError("can't save", f"fix the config file first ({e})", CONFIG) from None
        if "boxes" in data:
            return ({k: v for k, v in data.items() if k != "boxes"},
                    [dict(b) for b in data["boxes"]])
        if "host" not in data:
            return dict(data), []
        # The single-box form: the box's keys move into the list; the
        # YouTube mode stays on top as every box's default.
        box = {k: data[k] for k in BOX_KEYS if k in data and k != "youtubeMode"}
        top = {k: v for k, v in data.items() if k not in box}
        return top, [box]

    def _write(self, top, raw_boxes):
        data = {**top, "boxes": raw_boxes}
        configmod.parse(data, self.path)  # never write a file omakodi wouldn't read
        directory = os.path.dirname(self.path) or "."
        os.makedirs(directory, mode=0o700, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=directory, prefix=".config.")  # mode 600
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                f.write("\n")
            os.replace(tmp, self.path)
        except BaseException:
            try:
                os.remove(tmp)
            except OSError:
                pass
            raise

    def save(self, key, fields):
        """Add a box (``key`` "") or change the one whose host is ``key``,
        from the editor's ``fields`` (see ``editor_box``). Keys the editor
        doesn't show (eventPort, wakeOnLan, …) are kept. A new box, or the
        box in use, is the box in use afterwards. Returns its Config."""
        with self._lock:
            try:
                top, raw = self._read_raw()
                was = self.current().host if raw else None
                at = None
                if key:
                    at = next((i for i, b in enumerate(raw) if b.get("host") == key), None)
                    if at is None:
                        raise OmakodiError("can't save", "that box isn't in the config any more")
                box = editor_box(fields, raw[at] if at is not None else {})
                for i, other in enumerate(raw):
                    if i != at and str(other.get("host", "")).lower() == box["host"].lower():
                        raise OmakodiError("can't save", f"a box with the address {box['host']} is saved already")
                if at is None:
                    if len(raw) >= configmod.MAX_BOXES:
                        raise OmakodiError("can't save", f"at most {configmod.MAX_BOXES} boxes")
                    raw.append(box)
                else:
                    raw[at] = box
                self._write(top, raw)
                if at is None or was == key:
                    self.chosen.save(box["host"])
            except OSError as e:
                raise OmakodiError("can't save", e.strerror or str(e)) from None
        return self.find(box["host"])

    def delete(self, host):
        """Take the box whose host is ``host`` out of the config."""
        with self._lock:
            try:
                top, raw = self._read_raw()
                kept = [b for b in raw if b.get("host") != host]
                if len(kept) == len(raw):
                    raise OmakodiError("can't delete", "that box isn't in the config any more")
                self._write(top, kept)
            except OSError as e:
                raise OmakodiError("can't delete", e.strerror or str(e)) from None

    def password_of(self, host):
        """The saved password of the box at ``host`` ("" when none), for a
        test of its settings. Never leaves the daemon."""
        for cfg in self.boxes():
            if cfg.host == host:
                return cfg.password
        return ""


def editor_box(fields, saved):
    """The box's JSON object from the editor's ``fields``, on top of the
    ``saved`` one. A missing ``password`` keeps the saved one; an empty
    ``mac`` leaves waking to the MAC address read from Kodi. Raises
    OmakodiError (usage) for a field it can't take."""
    if not isinstance(fields, dict):
        raise OmakodiError("bad box", "the box must be a JSON object", USAGE)
    box = dict(saved)
    host = fields.get("host")
    host = host.strip() if isinstance(host, str) else ""
    if not configmod.HOST_RE.fullmatch(host):
        raise OmakodiError("bad address", "give the box's IP address or hostname (no http://, no port)", USAGE)
    box["host"] = host
    name = fields.get("name", "")
    box["name"] = one_line(name) or host
    for key, default in (("httpPort", 8080), ("tcpPort", 9090)):
        port = fields.get(key, default)
        if isinstance(port, str):
            text = port.strip()
            port = default if text == "" else int(text) if re.fullmatch(r"[0-9]{1,5}", text) else None
        if type(port) is not int or not 1 <= port <= 65535:
            label = "web port" if key == "httpPort" else "live port"
            raise OmakodiError("bad port", f"the {label} must be a number from 1 to 65535", USAGE)
        box[key] = port
    username = fields.get("username", "")
    if not isinstance(username, str) or len(username) > 1024:
        raise OmakodiError("bad username", "the username must be text", USAGE)
    box["username"] = username.strip()
    if "password" in fields:
        password = fields["password"]
        if not isinstance(password, str) or len(password) > 1024:
            raise OmakodiError("bad password", "the password must be text of up to 1024 characters", USAGE)
        box["password"] = password
    mac = fields.get("mac", "")
    mac = mac.strip() if isinstance(mac, str) else None
    if mac:
        parsed = parse_mac(mac)
        if parsed is None:
            raise OmakodiError("bad MAC address", "give it like aa:bb:cc:dd:ee:ff, or leave it empty", USAGE)
        box["mac"] = parsed
    elif mac == "":
        box.pop("mac", None)
    else:
        raise OmakodiError("bad MAC address", "the MAC address must be text", USAGE)
    if not box.get("username"):
        box.pop("username", None)
    if not box.get("password"):
        box.pop("password", None)
    return box


# ---- Test connection -------------------------------------------------------------


def test_box(fields, password=""):
    """Ask the box in the editor's ``fields`` who it is, with ``password``
    when the fields carry none. Returns {"message": "✓ Kodi 21.3", "name":
    Kodi's friendly name or "", "mac": its MAC address or ""}; raises
    OmakodiError with Kodi's answer otherwise."""
    if "password" not in fields:
        fields = {**fields, "password": password}
    box = editor_box(fields, {})
    cfg = Config(TEST_PATH, box["host"], http_port=box["httpPort"], tcp_port=box["tcpPort"],
                 username=box.get("username", ""), password=box.get("password", ""))
    kodi = Kodi(cfg)
    app = kodi.call("Application.GetProperties", {"properties": ["name", "version"]})
    app = app if isinstance(app, dict) else {}
    version = app.get("version") if isinstance(app.get("version"), dict) else {}
    major, minor = version.get("major"), version.get("minor")
    name = one_line(app.get("name"), 40) or "Kodi"
    number = f" {major}.{minor}" if type(major) is int and type(minor) is int else ""
    try:
        labels = kodi.call("XBMC.GetInfoLabels", {"labels": ["System.FriendlyName", "Network.MacAddress"]})
    except OmakodiError:
        labels = None
    labels = labels if isinstance(labels, dict) else {}
    return {
        "message": f"\u2713 {name}{number}",
        "name": one_line(labels.get("System.FriendlyName")),
        "mac": parse_mac(labels.get("Network.MacAddress")) or "",
    }


# ---- Found on your network ---------------------------------------------------------

_ESCAPE = re.compile(r"\\(\d{3}|.)")


def _unescape(value):
    """avahi-browse -p writes odd characters as \\DDD (decimal) or \\c."""
    return _ESCAPE.sub(lambda m: chr(int(m.group(1))) if m.group(1).isdigit() and int(m.group(1)) < 256
                       else m.group(1), value)


def parse_avahi(text):
    """The resolved IPv4 services in ``avahi-browse -rpt`` output: a list of
    {"name", "hostname", "address", "port", "uuid"}."""
    found = []
    for line in str(text).splitlines():
        parts = line.split(";")
        if len(parts) < 9 or parts[0] != "=" or parts[2] != "IPv4":
            continue
        address, port = parts[7], parts[8]
        if not IPV4_RE.match(address) or not port.isdigit() or not 1 <= int(port) <= 65535:
            continue
        uuid = ""
        txt = ";".join(parts[9:])
        m = re.search(r'"uuid=([0-9A-Za-z-]{1,64})"', txt)
        if m:
            uuid = m.group(1).lower()
        hostname = _unescape(parts[6]).rstrip(".")
        found.append({
            "name": one_line(_unescape(parts[3])),
            "hostname": hostname if configmod.HOST_RE.fullmatch(hostname) else "",
            "address": address,
            "port": int(port),
            "uuid": uuid,
        })
    return found


def merge_found(http, tcp):
    """The boxes from the web-server and TCP announcements: one per box
    (its uuid, else its address), the live port from the TCP one."""
    tcp_port = {}
    for s in tcp:
        tcp_port.setdefault(s["uuid"] or s["address"], s["port"])
    boxes = {}
    for s in http:
        key = s["uuid"] or s["address"]
        if key in boxes:
            continue
        boxes[key] = {
            "name": s["name"] or s["hostname"] or s["address"],
            "host": s["address"],
            "hostname": s["hostname"],
            "httpPort": s["port"],
            "tcpPort": tcp_port.get(key, 9090),
        }
    return sorted(boxes.values(), key=lambda b: (b["name"].lower(), b["host"]))[:MAX_FOUND]


def new_boxes(found, saved):
    """The found boxes that aren't saved: none whose address or hostname and
    web port match a saved box's."""
    taken = {(c.host.lower(), c.http_port) for c in saved}
    return [{k: b[k] for k in ("name", "host", "httpPort", "tcpPort")} for b in found
            if (b["host"].lower(), b["httpPort"]) not in taken
            and not (b["hostname"] and (b["hostname"].lower(), b["httpPort"]) in taken)]


def _browse(service, timeout):
    program = shutil.which("avahi-browse") or "/usr/bin/avahi-browse"
    try:
        done = subprocess.run([program, "--resolve", "--parsable", "--terminate", service],
                              stdin=subprocess.DEVNULL, capture_output=True, timeout=timeout)
    except FileNotFoundError:
        raise OmakodiError("can't search the network", "avahi-browse isn't installed (the avahi package)") from None
    except subprocess.TimeoutExpired:
        raise OmakodiError("can't search the network", "avahi-browse took too long") from None
    except OSError as e:
        raise OmakodiError("can't search the network", e.strerror or str(e)) from None
    if done.returncode != 0:
        err = done.stderr.decode("utf-8", "replace")
        if "not running" in err.lower():
            raise OmakodiError("can't search the network",
                               "the avahi daemon isn't running (systemctl enable --now avahi-daemon)")
        raise OmakodiError("can't search the network", one_line(err, 200) or f"avahi-browse failed ({done.returncode})")
    return done.stdout[:MAX_OUTPUT].decode("utf-8", "replace")


def discover(browse=_browse, timeout=SEARCH_TIMEOUT):
    """Kodi boxes announcing themselves on the local network (zeroconf,
    through avahi-browse). Nothing is sent to them: no login, no password."""
    results, errors = {}, []

    def one(service):
        try:
            results[service] = parse_avahi(browse(service, timeout))
        except OmakodiError as e:
            errors.append(e)

    threads = [threading.Thread(target=one, args=(s,), daemon=True) for s in (HTTP_SERVICE, TCP_SERVICE)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout + 1)
    if HTTP_SERVICE not in results:
        raise errors[0] if errors else OmakodiError("can't search the network", "avahi-browse took too long")
    return merge_found(results[HTTP_SERVICE], results.get(TCP_SERVICE, []))


def box_list(boxes, current, macs=None):
    """The state's ``boxes``: the box in use and every box's editable
    settings. Passwords are never in it, only whether one is saved."""
    return {
        "current": current.host if current is not None else "",
        "list": [{
            "name": one_line(c.name) or c.host,
            "host": c.host,
            "httpPort": c.http_port,
            "tcpPort": c.tcp_port,
            "username": one_line(c.username, 100),
            "hasPassword": bool(c.password),
            "mac": c.mac,
            "knownMac": (macs.read(c.host) or "") if macs is not None else "",
        } for c in boxes],
    }
