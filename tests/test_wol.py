"""Wake-on-LAN (ticket 029): the MAC address, the magic packet, mac.json."""

import json
import os
import socket
import stat
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "lib"))

from omakodi import wol  # noqa: E402
from omakodi.config import Config  # noqa: E402
from omakodi.errors import OmakodiError  # noqa: E402

MAC = "02:1a:2b:3c:4d:5e"


class MacTest(unittest.TestCase):
    def test_valid(self):
        for value in ("02:1a:2b:3c:4d:5e", "02-1A-2B-3C-4D-5E", "02:1A:2b:3C:4d:5E"):
            self.assertEqual(wol.parse_mac(value), MAC)

    def test_refused(self):
        for value in (None, 7, "", "Busy", "02:1a:2b:3c:4d", "02:1a:2b:3c:4d:5e:6f", "02:1a-2b:3c:4d:5e",
                      "021a2b3c4d5e", "02:1a:2b:3c:4d:5g", " 02:1a:2b:3c:4d:5e", "02:1a:2b:3c:4d:5e\n",
                      "02:1a:2b:3c:4d:5e ", "２2:1a:2b:3c:4d:5e",
                      "00:00:00:00:00:00",  # no box has it
                      "ff:ff:ff:ff:ff:ff", "01:00:5e:00:00:01", "33:33:00:00:00:01"):  # multicast
            self.assertIsNone(wol.parse_mac(value), value)

    def test_magic_packet(self):
        packet = wol.magic_packet("02-1A-2B-3C-4D-5E")
        self.assertEqual(len(packet), 102)
        self.assertEqual(packet[:6], b"\xff" * 6)
        self.assertEqual(packet[6:], bytes([0x02, 0x1A, 0x2B, 0x3C, 0x4D, 0x5E]) * 16)


class FakeSocket:
    def __init__(self, fail=None):
        self.options, self.sent, self.closed, self.fail = [], [], False, fail

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.closed = True

    def setsockopt(self, level, name, value):
        self.options.append((level, name, value))

    def sendto(self, data, address):
        if self.fail:
            raise self.fail
        self.sent.append((data, address))


class SendTest(unittest.TestCase):
    def test_broadcast_three_times(self):
        s = FakeSocket()
        wol.send_packet(b"packet", make_socket=lambda: s)
        self.assertIn((socket.SOL_SOCKET, socket.SO_BROADCAST, 1), s.options)
        self.assertEqual(s.sent, [(b"packet", ("255.255.255.255", 9))] * 3)
        self.assertTrue(s.closed)

    def test_failure(self):
        s = FakeSocket(fail=OSError(101, "Network is unreachable"))
        with self.assertRaises(OmakodiError) as cm:
            wol.send_packet(b"packet", make_socket=lambda: s)
        self.assertEqual(str(cm.exception), "can't wake Kodi: sending the packet failed (Network is unreachable)")
        self.assertTrue(s.closed)


class StoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = os.path.join(self.tmp.name, "omakodi")
        self.store = wol.MacStore(self.dir)

    def tearDown(self):
        self.tmp.cleanup()

    def test_saved_for_its_host(self):
        self.assertIsNone(self.store.read("kodi.example.lan"))
        self.assertTrue(self.store.save("kodi.example.lan", "02-1A-2B-3C-4D-5E"))
        self.assertEqual(stat.S_IMODE(os.stat(self.store.path).st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(os.stat(self.dir).st_mode), 0o700)
        with open(self.store.path) as f:
            self.assertEqual(json.load(f), {"boxes": {"kodi.example.lan": MAC}})
        self.assertEqual(self.store.read("kodi.example.lan"), MAC)
        self.assertIsNone(self.store.read("other.example.lan"))  # another box
        self.assertEqual(os.listdir(self.dir), ["mac.json"])  # no temp file left

    def test_every_box_keeps_its_own(self):
        other = "02:00:00:00:00:07"
        self.store.save("kodi.example.lan", MAC)
        self.store.save("bedroom.example.lan", other)
        self.assertEqual(self.store.read("kodi.example.lan"), MAC)
        self.assertEqual(self.store.read("bedroom.example.lan"), other)
        for i in range(40):  # the 32 most recently changed are kept
            self.store.save(f"box{i}.example.lan", other)
        self.assertIsNone(self.store.read("kodi.example.lan"))
        self.assertEqual(self.store.read("box39.example.lan"), other)
        self.assertIsNone(self.store.read("box7.example.lan"))
        self.assertEqual(self.store.read("box8.example.lan"), other)

    def test_reads_the_single_box_file_of_0_2(self):
        os.makedirs(self.dir)
        with open(self.store.path, "w") as f:
            json.dump({"host": "kodi.example.lan", "mac": MAC}, f)
        self.assertEqual(self.store.read("kodi.example.lan"), MAC)
        self.store.save("bedroom.example.lan", "02:00:00:00:00:07")
        self.assertEqual(self.store.read("kodi.example.lan"), MAC)  # carried over

    def test_written_only_when_it_changes(self):
        self.store.save("kodi.example.lan", MAC)
        before = os.stat(self.store.path).st_ino
        self.assertFalse(self.store.save("kodi.example.lan", MAC.upper()))
        self.assertEqual(os.stat(self.store.path).st_ino, before)
        self.assertTrue(self.store.save("kodi.example.lan", "02:00:00:00:00:01"))
        self.assertEqual(self.store.read("kodi.example.lan"), "02:00:00:00:00:01")

    def test_bad_addresses_and_files(self):
        self.assertFalse(self.store.save("kodi.example.lan", "Busy"))
        self.assertFalse(os.path.exists(self.store.path))
        os.makedirs(self.dir)
        for junk in (b"not json", b"[1]", b'{"host": "kodi.example.lan", "mac": "ff:ff:ff:ff:ff:ff"}',
                     b'{"host": "kodi.example.lan"}', b"\xff\xfe", b" " * 5000):
            with open(self.store.path, "wb") as f:
                f.write(junk)
            self.assertIsNone(self.store.read("kodi.example.lan"), junk[:40])


class HostValueTest(unittest.TestCase):
    """state.HostValue: what the daemon learnt about a box (volume.json)."""

    def test_kept_per_host(self):
        from omakodi.state import HostValue
        with tempfile.TemporaryDirectory() as d:
            store = HostValue("volume", "keys", ("kodi", "tv"), os.path.join(d, "omakodi"))
            self.assertIsNone(store.read("kodi.example.lan"))
            self.assertTrue(store.save("kodi.example.lan", "tv"))
            self.assertFalse(store.save("kodi.example.lan", "tv"))
            self.assertEqual(stat.S_IMODE(os.stat(store.path).st_mode), 0o600)
            with open(store.path) as f:
                self.assertEqual(json.load(f), {"boxes": {"kodi.example.lan": "tv"}})
            self.assertEqual(store.read("kodi.example.lan"), "tv")
            self.assertIsNone(store.read("other.example.lan"))
            self.assertTrue(store.save("other.example.lan", "kodi"))
            self.assertEqual((store.read("kodi.example.lan"), store.read("other.example.lan")), ("tv", "kodi"))
            with self.assertRaises(ValueError):
                store.save("kodi.example.lan", "soundbar")
            with open(store.path, "w") as f:
                json.dump({"host": "kodi.example.lan", "keys": "soundbar"}, f)
            self.assertIsNone(store.read("kodi.example.lan"))
            with open(store.path, "w") as f:  # omakodi 0.2's single-box file
                json.dump({"host": "kodi.example.lan", "keys": "tv"}, f)
            self.assertEqual(store.read("kodi.example.lan"), "tv")
            self.assertEqual(os.listdir(os.path.dirname(store.path)), ["volume.json"])


class WakeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = wol.MacStore(self.tmp.name)
        self.sent = []

    def tearDown(self):
        self.tmp.cleanup()

    def wake(self, **kw):
        return wol.wake(Config("(test)", "kodi.example.lan", **kw), self.store, send=self.sent.append)

    def test_the_saved_mac(self):
        self.store.save("kodi.example.lan", MAC)
        self.assertEqual(self.wake(), MAC)
        self.assertEqual(self.sent, [wol.magic_packet(MAC)])

    def test_the_config_wins(self):
        self.store.save("kodi.example.lan", MAC)
        self.assertEqual(self.wake(mac="02:00:00:00:00:01"), "02:00:00:00:00:01")
        self.assertEqual(self.sent, [wol.magic_packet("02:00:00:00:00:01")])

    def test_no_mac_known(self):
        # The phone remote's words, naming the box (ticket 053).
        with self.assertRaises(OmakodiError) as cm:
            self.wake(name="Living room")
        self.assertEqual(str(cm.exception), "No MAC address saved for Living room. Connect once while it's on, "
                                            "or add it in the box's settings.")
        self.assertEqual(cm.exception.code, 1)
        self.assertEqual(self.sent, [])

    def test_an_invalid_mac(self):
        # The config and mac.json refuse one when read; wake checks again.
        with self.assertRaises(OmakodiError) as cm:
            self.wake(name="Living room", mac="01:00:5e:00:00:01")  # multicast: not a box's
        self.assertEqual(str(cm.exception), "Invalid MAC address for Living room")
        self.assertEqual(self.sent, [])

    def test_turned_off(self):
        self.store.save("kodi.example.lan", MAC)
        with self.assertRaises(OmakodiError) as cm:
            self.wake(mac=MAC, wake_on_lan=False)
        self.assertEqual(str(cm.exception), "can't wake Kodi: \"wakeOnLan\" is false in the config")
        self.assertIsNone(wol.mac_for(Config("(test)", "kodi.example.lan", wake_on_lan=False), self.store))
        self.assertEqual(self.sent, [])


class CommandTest(unittest.TestCase):
    def test_wake_without_a_mac(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = os.path.join(d, "config.json")
            with open(cfg, "w") as f:
                json.dump({"host": "kodi.example.lan"}, f)
            env = dict(os.environ, OMAKODI_CONFIG=cfg, XDG_STATE_HOME=d)
            p = subprocess.run([os.path.join(ROOT, "bin", "omakodi"), "wake"], capture_output=True, text=True,
                               env=env, timeout=10)
        self.assertEqual(p.returncode, 1)
        self.assertEqual(p.stderr, "omakodi: No MAC address saved for kodi.example.lan. Connect once while it's on, "
                                   "or add it in the box's settings.\n")


if __name__ == "__main__":
    unittest.main()
