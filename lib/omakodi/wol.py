"""Wake-on-LAN (SPEC "Power", "Wake-on-LAN").

The daemon reads the box's MAC address from Kodi while it answers and keeps
it per box in ~/.local/state/omakodi/mac.json; ``wake`` sends
the magic packet to the broadcast address.
"""

import re
import socket

from .errors import OmakodiError
from .state import HostMap

BROADCAST = "255.255.255.255"
PORT = 9
SENDS = 3  # UDP can drop one; the box ignores the extra ones
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
    """Each box's MAC address, per host, in mac.json (mode 600; see
    state.HostMap)."""

    def __init__(self, directory=None):
        self._map = HostMap("mac", parse_mac, key="mac", directory=directory)
        self.path = self._map.path

    def read(self, host):
        return self._map.read(host)

    def save(self, host, mac):
        """Keep ``mac`` for ``host``; writes only when it changes."""
        if parse_mac(mac) is None:
            return False
        return self._map.save(host, mac)


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
