"""Kodi's EventServer (SPEC "The soundbar over HDMI-CEC").

JSON-RPC can't run Kodi's builtins; the EventServer (UDP, 9777) can. One
PT_ACTION packet, no HELO first (Kodi runs actions without one, and a HELO
shows "new connection" on the TV).
"""

import socket
import struct

from .errors import UNREACHABLE, OmakodiError
from .rpc import bad_address, is_address

PT_ACTION = 0x0A
ACTION_BUILTIN = 0x01
HEADER_SIZE = 32
PACKET_SIZE = 1024
# signature, major, minor, type, sequence, packets, payload size, client token
HEADER = struct.Struct("!4sBBHIIHI")
SOUNDBAR_ON = "CECActivateSource"


def action_packet(builtin):
    """A PT_ACTION packet that runs ``builtin``."""
    name = builtin.encode("ascii")
    if b"\0" in name:
        raise ValueError("builtin with a zero byte")
    payload = bytes([ACTION_BUILTIN]) + name + b"\0"
    if HEADER_SIZE + len(payload) > PACKET_SIZE:
        raise ValueError("builtin too long")
    # Token 0: Kodi tells clients apart by address.
    header = HEADER.pack(b"XBMC", 2, 0, PT_ACTION, 1, 1, len(payload), 0) + b"\0" * 10
    return header + payload


class EventServerError(OmakodiError):
    """The packet couldn't be sent; ``why`` is the system's reason
    ("Network is unreachable"), which the message gives (SPEC "Messages")."""

    def __init__(self, host, port, why):
        self.why = why
        super().__init__("can't reach Kodi's EventServer", f"{host}:{port} ({why})", UNREACHABLE)


def send_packet(host, port, packet, make_socket=None):
    make_socket = make_socket or (lambda: socket.socket(socket.AF_INET, socket.SOCK_DGRAM))
    try:
        with make_socket() as s:
            s.sendto(packet, (host, port))
    except OSError as e:
        raise EventServerError(host, port, str(e.strerror or e)) from None


def run_builtin(cfg, builtin, send=send_packet):
    if not is_address(cfg.host):
        raise bad_address(cfg)
    try:
        send(cfg.host, cfg.event_port, action_packet(builtin))
    except OmakodiError as e:
        e.box = e.box or cfg.name
        raise
