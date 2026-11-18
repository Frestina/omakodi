"""Wake-on-LAN (SPEC "Power", "Wake-on-LAN").

The daemon reads the box's MAC address from Kodi while it answers and keeps
it in ~/.local/state/omakodi/mac.json for the config's host; ``wake`` sends
the magic packet to the broadcast address.
"""

import json
import os
import re
import socket
import tempfile
import threading

from .errors import OmakodiError
from .state import state_dir

BROADCAST = "255.255.255.255"
PORT = 9
SENDS = 3  # UDP can drop one; the box ignores the extra ones
MAX_FILE = 4 * 1024
MAC_RE = re.compile(r"[0-9a-f]{2}([:-])[0-9a-f]{2}(\1[0-9a-f]{2}){4}", re.IGNORECASE)
SENT = "Wake-up sent; Kodi takes a minute to start"


def parse_mac(value):
    """``value`` as "aa:bb:cc:dd:ee:ff", or None when it isn't a box's MAC
    address (not six hex pairs, all zeros, or multicast)."""
    if not isinstance(value, str) or not MAC_RE.fullmatch(value):
        return None
    mac = value.lower().replace("-", ":")
    first = int(mac[:2], 16)
    if mac == "00:00:00:00:00:00" or first & 1:
        return None
    return mac


def magic_packet(mac):
    """6 bytes ff, then the MAC 16 times: 102 bytes."""
    raw = bytes.fromhex(parse_mac(mac).replace(":", ""))
    return b"\xff" * 6 + raw * 16


def send_packet(packet, address=BROADCAST, port=PORT, make_socket=None):
    make_socket = make_socket or (lambda: socket.socket(socket.AF_INET, socket.SOCK_DGRAM))
    try:
        with make_socket() as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            for _ in range(SENDS):
                s.sendto(packet, (address, port))
    except OSError as e:
        raise OmakodiError("can't wake Kodi", f"sending the packet failed ({e.strerror or e})") from None


class MacStore:
    """The box's MAC address for one host, in mac.json (mode 600)."""

    def __init__(self, directory=None):
        self.path = os.path.join(directory or state_dir(), "mac.json")
        self._lock = threading.Lock()

    def read(self, host):
        try:
            with open(self.path, "rb") as f:
                raw = f.read(MAX_FILE + 1)
            data = json.loads(raw.decode("utf-8")) if len(raw) <= MAX_FILE else None
        except (OSError, UnicodeDecodeError, ValueError):
            return None
        if not isinstance(data, dict) or data.get("host") != host:
            return None
        return parse_mac(data.get("mac"))

    def save(self, host, mac):
        """Keep ``mac`` for ``host``; writes only when it changes."""
        mac = parse_mac(mac)
        if mac is None:
            return False
        with self._lock:
            if self.read(host) == mac:
                return False
            directory = os.path.dirname(self.path)
            os.makedirs(directory, mode=0o700, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=directory, prefix=".mac.")  # mode 600
            try:
                with os.fdopen(fd, "w") as f:
                    json.dump({"host": host, "mac": mac}, f)
                    f.write("\n")
                os.replace(tmp, self.path)
            except BaseException:
                try:
                    os.remove(tmp)
                except OSError:
                    pass
                raise
        return True


def mac_for(cfg, store):
    """The MAC address to wake ``cfg``'s box with, or None."""
    if not cfg.wake_on_lan:
        return None
    return cfg.mac or store.read(cfg.host)


def wake(cfg, store, send=send_packet):
    """Send the magic packet for ``cfg``'s box. Returns the MAC it used."""
    if not cfg.wake_on_lan:
        raise OmakodiError("can't wake Kodi", '"wakeOnLan" is false in the config')
    mac = mac_for(cfg, store)
    if mac is None:
        raise OmakodiError("can't wake Kodi", "no MAC address known yet; connect once while Kodi is on, "
                                              'or set "mac" in the config')
    send(magic_packet(mac))
    return mac
