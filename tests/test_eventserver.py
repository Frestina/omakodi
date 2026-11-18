"""Kodi's EventServer packet for turning on the soundbar (ticket 030)."""

import os
import struct
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "lib"))

from omakodi import eventserver  # noqa: E402
from omakodi.config import Config  # noqa: E402
from omakodi.control import Controller  # noqa: E402
from omakodi.errors import UNREACHABLE, OmakodiError  # noqa: E402
from omakodi.rpc import Kodi  # noqa: E402


def kodi_parse(data):
    """Kodi's CEventPacket::Parse and OnPacketACTION (Omega), for checking:
    returns (type, token, action type, action) or None if Kodi drops it."""
    if len(data) < 32 or len(data) > 1024 or data[:4] != b"XBMC":
        return None
    major, minor, ptype, seq, total, size, token = struct.unpack("!BBHIIHI", data[4:22])
    if major != 2 and minor != 0:
        return None
    if size + 32 != len(data):
        return None
    payload = data[32:]
    if not payload or b"\0" not in payload[1:]:
        return None
    return ptype, token, payload[0], payload[1:payload.index(b"\0", 1)].decode()


class PacketTest(unittest.TestCase):
    def test_bytes(self):
        packet = eventserver.action_packet("CECActivateSource")
        self.assertEqual(packet, (
            b"XBMC" b"\x02\x00"       # signature, version 2.0
            b"\x00\x0a"               # PT_ACTION
            b"\x00\x00\x00\x01"       # sequence 1
            b"\x00\x00\x00\x01"       # 1 packet
            b"\x00\x13"               # payload: 19 bytes
            b"\x00\x00\x00\x00"       # client token 0: Kodi goes by address
            + b"\x00" * 10            # reserved
            + b"\x01" b"CECActivateSource\x00"))  # run a builtin
        self.assertEqual(kodi_parse(packet), (0x0A, 0, 0x01, "CECActivateSource"))

    def test_refused_builtins(self):
        for bad in ("a\0b", "x" * 1000, "Ä"):
            with self.assertRaises((ValueError, UnicodeEncodeError)):
                eventserver.action_packet(bad)


class FakeSocket:
    def __init__(self, fail=None):
        self.sent, self.closed, self.fail = [], False, fail

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.closed = True

    def sendto(self, data, address):
        if self.fail:
            raise self.fail
        self.sent.append((data, address))


class SendTest(unittest.TestCase):
    def test_one_packet_to_the_event_port(self):
        s = FakeSocket()
        eventserver.send_packet("kodi.example.lan", 9777, b"packet", make_socket=lambda: s)
        self.assertEqual(s.sent, [(b"packet", ("kodi.example.lan", 9777))])
        self.assertTrue(s.closed)

    def test_failure(self):
        s = FakeSocket(fail=OSError(-2, "Name or service not known"))
        with self.assertRaises(OmakodiError) as cm:
            eventserver.send_packet("kodi.example.lan", 9777, b"packet", make_socket=lambda: s)
        self.assertEqual(str(cm.exception),
                         "can't reach Kodi's EventServer: kodi.example.lan:9777 (Name or service not known)")
        self.assertEqual(cm.exception.code, UNREACHABLE)

    def test_soundbaron_action(self):
        sent = []
        cfg = Config("(test)", "kodi.example.lan", event_port=9800, password="example-password", username="kodi")
        Controller(Kodi(cfg), event_send=lambda *a: sent.append(a)).run("soundbaron")
        self.assertEqual(sent, [("kodi.example.lan", 9800, eventserver.action_packet("CECActivateSource"))])
        self.assertNotIn(b"example-password", sent[0][2])  # no login on the EventServer


if __name__ == "__main__":
    unittest.main()
