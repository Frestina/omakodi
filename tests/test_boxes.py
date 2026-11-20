"""Several Kodi boxes (ticket 042): the config's list and its old single-box
form, the box in use, saving and deleting boxes, Test connection, finding
boxes on the network, and the daemon switching between two fake Kodis."""

import json
import os
import stat
import subprocess
import sys
import tempfile
import threading
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fakekodi import ROOT, FakeKodi  # noqa: E402
from test_daemon import Lines  # noqa: E402
from omakodi import boxes, config, daemon  # noqa: E402
from omakodi.art import ArtCache  # noqa: E402
from omakodi.errors import CONFIG, OmakodiError  # noqa: E402
from omakodi.shortcuts import ShortcutStore  # noqa: E402
from omakodi.state import ChosenBox, HostValue, StopNote, YoutubeHealth  # noqa: E402
from omakodi.titles import TitleStore  # noqa: E402
from omakodi.wol import MacStore  # noqa: E402
from omakodi.youtubemode import mode_store  # noqa: E402

SECRET = "s3cret-example-pw"
OTHER_SECRET = "an0ther-example-pw"

# avahi-browse -rpt output, fictional: two boxes, one on two interfaces,
# one IPv6 line, and an unresolved "+" line.
AVAHI_HTTP = """+;eth0;IPv4;Living\\032room;_xbmc-jsonrpc-h._tcp;local
=;eth0;IPv4;Living\\032room;_xbmc-jsonrpc-h._tcp;local;kodi.local;192.0.2.10;8080;"txtvers=1" "uuid=11111111-aaaa-bbbb-cccc-000000000001"
=;wlan0;IPv4;Living\\032room;_xbmc-jsonrpc-h._tcp;local;kodi.local;192.0.2.10;8080;"txtvers=1" "uuid=11111111-aaaa-bbbb-cccc-000000000001"
=;eth0;IPv6;Living\\032room;_xbmc-jsonrpc-h._tcp;local;kodi.local;fe80::1;8080;"txtvers=1" "uuid=11111111-aaaa-bbbb-cccc-000000000001"
=;eth0;IPv4;Kodi\\032\\040Bedroom\\041;_xbmc-jsonrpc-h._tcp;local;bedroom.local;192.0.2.20;8081;"uuid=22222222-aaaa-bbbb-cccc-000000000002"
=;eth0;IPv4;broken;_xbmc-jsonrpc-h._tcp;local;x.local;not-an-address;8080;
"""
AVAHI_TCP = """=;eth0;IPv4;Living\\032room;_xbmc-jsonrpc._tcp;local;kodi.local;192.0.2.10;9091;"uuid=11111111-aaaa-bbbb-cccc-000000000001"
"""


class Files(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "config", "config.json")
        self.state = os.path.join(self.tmp.name, "state")
        self.chosen = ChosenBox(self.state)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, data, mode=0o600):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w") as f:
            f.write(data if isinstance(data, str) else json.dumps(data))
        os.chmod(self.path, mode)

    def read(self):
        with open(self.path) as f:
            return json.load(f)


class ConfigFormsTest(Files):
    def test_the_single_box_form_still_works(self):
        self.write({"host": "kodi.example.lan", "username": "kodi", "password": SECRET, "mac": "02:00:00:00:00:01"})
        (box,) = config.load_all(self.path)
        self.assertEqual((box.host, box.name, box.password, box.mac), ("kodi.example.lan", "kodi.example.lan",
                                                                       SECRET, "02:00:00:00:00:01"))
        self.assertEqual(config.load(self.path, chosen="anything").host, "kodi.example.lan")

    def test_a_list_and_the_box_in_use(self):
        self.write({"youtubeMode": "youtube-first", "boxes": [
            {"name": "Living room", "host": "kodi.example.lan", "password": SECRET},
            {"name": "Bedroom", "host": "bedroom.example.lan", "httpPort": 8081, "wakeOnLan": False,
             "youtubeMode": "sendtokodi-only"}]})
        a, b = config.load_all(self.path)
        self.assertEqual((a.name, a.youtube_mode, a.wake_on_lan), ("Living room", "youtube-first", True))
        self.assertEqual((b.name, b.http_port, b.youtube_mode, b.wake_on_lan),
                         ("Bedroom", 8081, "sendtokodi-only", False))
        self.assertEqual(config.load(self.path, chosen="bedroom.example.lan").name, "Bedroom")
        self.assertEqual(config.load(self.path, chosen="gone.example.lan").name, "Living room")  # the first

    def test_bad_lists(self):
        for data in (
            {"host": "kodi.example.lan", "boxes": []},
            {"boxes": {}},
            {"boxes": ["kodi.example.lan"]},
            {"boxes": [{"host": "kodi.example.lan"}, {"host": "KODI.example.lan"}]},  # no ids: one host
            {"boxes": [{"id": "a1", "host": "kodi.example.lan"}, {"id": "a1", "host": "b.example.lan"}]},
            {"boxes": [{"id": "kodi", "host": "a.example.lan"}, {"host": "Kodi"}]},  # an id that is a host
            {"boxes": [{"id": "", "host": "kodi.example.lan"}]},
            {"boxes": [{"id": "a/b", "host": "kodi.example.lan"}]},
            {"boxes": [{"id": 5, "host": "kodi.example.lan"}]},
            {"boxes": [{"host": "kodi.example.lan", "name": "two\nlines"}]},
            {"boxes": [{"host": "kodi.example.lan", "name": 5}]},
            {"boxes": [{"host": "kodi.example.lan"}, {"host": "x/y"}]},
            {"boxes": [{"host": f"box{i}.example.lan"} for i in range(33)]},
        ):
            self.write(data)
            with self.assertRaises(OmakodiError, msg=data) as cm:
                config.load_all(self.path)
            self.assertEqual((cm.exception.kind, cm.exception.code), ("bad config", CONFIG))

    def test_boxes_are_known_by_their_id(self):
        self.write({"boxes": [{"id": "a1", "name": "Living room", "host": "kodi.example.lan"},
                              {"id": "b2", "name": "Kodi on 8081", "host": "kodi.example.lan", "httpPort": 8081},
                              {"name": "Old", "host": "old.example.lan"}]})
        a, b, old = config.load_all(self.path)  # two boxes on one address
        self.assertEqual([(c.id, c.saved_id) for c in (a, b, old)],
                         [("a1", True), ("b2", True), ("old.example.lan", False)])  # no id: its host
        self.assertEqual(config.load(self.path, chosen="b2").name, "Kodi on 8081")
        self.assertEqual(config.load(self.path, chosen="kodi.example.lan").name, "Living room")  # box.json of 042
        self.assertEqual(config.load(self.path, chosen="old.example.lan").name, "Old")

    def test_an_empty_list_is_not_configured(self):
        self.write({"boxes": []})
        self.assertEqual(config.load_all(self.path), [])
        with self.assertRaises(OmakodiError) as cm:
            config.load(self.path, chosen="")
        self.assertEqual(cm.exception.kind, "not configured")

    def test_any_box_with_a_password_needs_mode_600(self):
        self.write({"boxes": [{"host": "kodi.example.lan"}, {"host": "b.example.lan", "password": SECRET}]}, 0o644)
        with self.assertRaises(OmakodiError) as cm:
            config.load_all(self.path)
        self.assertEqual(cm.exception.kind, "config readable by others")
        self.assertNotIn(SECRET, str(cm.exception))


class BoxBookTest(Files):
    def book(self):
        return boxes.BoxBook(self.path, self.chosen)

    def ids(self):
        """The boxes' ids in the file, checked to be new UUIDs, each its own."""
        found = [b["id"] for b in self.read()["boxes"]]
        for box_id in found:
            self.assertRegex(box_id, r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")
        self.assertEqual(len(set(found)), len(found))
        return found

    def test_adding_a_box_turns_the_old_form_into_a_list(self):
        self.write({"host": "kodi.example.lan", "username": "kodi", "password": SECRET, "wakeOnLan": False,
                    "youtubeMode": "youtube-first", "eventPort": 9778})
        book = self.book()
        saved = book.save("", {"name": "Bedroom", "host": " bedroom.example.lan ", "httpPort": "8081",
                               "tcpPort": 9090, "username": "", "password": OTHER_SECRET})
        self.assertEqual((saved.name, saved.host, saved.http_port), ("Bedroom", "bedroom.example.lan", 8081))
        old, new = self.ids()  # the old box got its id before the new one was added
        self.assertEqual(saved.id, new)
        self.assertEqual(self.read(), {"youtubeMode": "youtube-first", "boxes": [
            {"id": old, "host": "kodi.example.lan", "username": "kodi", "password": SECRET, "wakeOnLan": False,
             "eventPort": 9778},
            {"id": new, "host": "bedroom.example.lan", "name": "Bedroom", "httpPort": 8081, "tcpPort": 9090,
             "password": OTHER_SECRET}]})
        self.assertEqual(stat.S_IMODE(os.stat(self.path).st_mode), 0o600)
        self.assertEqual(os.listdir(os.path.dirname(self.path)), ["config.json"])  # no temp file left
        self.assertEqual(self.chosen.read(), new)  # a new box is the one in use
        first = config.load(self.path, chosen=old)  # the old box is as it was
        self.assertEqual((first.password, first.wake_on_lan, first.event_port, first.youtube_mode),
                         (SECRET, False, 9778, "youtube-first"))

    def test_the_first_box_makes_the_file(self):
        saved = self.book().save("", {"name": "", "host": "kodi.example.lan"})
        self.assertEqual(saved.name, "kodi.example.lan")  # no name: its address
        (box_id,) = self.ids()
        self.assertEqual(self.read(), {"boxes": [{"id": box_id, "host": "kodi.example.lan",
                                                  "name": "kodi.example.lan", "httpPort": 8080, "tcpPort": 9090}]})
        self.assertEqual(stat.S_IMODE(os.stat(os.path.dirname(self.path)).st_mode), 0o700)

    def test_editing_keeps_the_password_and_what_the_editor_doesnt_show(self):
        self.write({"boxes": [{"id": "a1", "name": "Living room", "host": "kodi.example.lan", "username": "kodi",
                               "password": SECRET, "wakeOnLan": False, "custom": 1}]})
        self.chosen.save("a1")
        book = self.book()
        book.save("a1", {"name": "Lounge", "host": "kodi2.example.lan", "httpPort": 8080,
                         "tcpPort": 9090, "username": "kodi", "mac": "02-00-00-00-00-09"})
        (box,) = self.read()["boxes"]
        self.assertEqual(box, {"id": "a1", "name": "Lounge", "host": "kodi2.example.lan", "username": "kodi",
                               "password": SECRET, "wakeOnLan": False, "custom": 1, "httpPort": 8080,
                               "tcpPort": 9090, "mac": "02:00:00:00:00:09"})
        self.assertEqual(self.chosen.read(), "a1")  # still the box in use
        book.save("a1", {"host": "kodi2.example.lan", "password": "", "mac": ""})
        (box,) = self.read()["boxes"]
        self.assertNotIn("password", box)  # emptied on purpose
        self.assertNotIn("mac", box)

    def test_an_older_remote_names_the_box_by_its_host(self):
        self.write({"boxes": [{"id": "a1", "host": "kodi.example.lan"}, {"id": "b2", "host": "bedroom.example.lan"}]})
        book = self.book()
        self.assertEqual(book.save("bedroom.example.lan", {"name": "Bedroom", "host": "bedroom.example.lan"}).id, "b2")
        self.assertEqual(book.use("kodi.example.lan").id, "a1")
        self.assertEqual(self.chosen.read(), "a1")
        book.delete("bedroom.example.lan")
        self.assertEqual([b["id"] for b in self.read()["boxes"]], ["a1"])

    def test_two_boxes_on_one_address(self):
        self.write({"boxes": [{"id": "a1", "name": "Living room", "host": "kodi.example.lan"}]})
        book = self.book()
        other = book.save("", {"name": "Living room again", "host": "KODI.example.lan"})  # no check for duplicates
        self.assertNotEqual(other.id, "a1")
        self.assertEqual([c.name for c in book.boxes()], ["Living room", "Living room again"])
        self.assertEqual(book.current().id, other.id)
        book.save("a1", {"name": "Lounge", "host": "kodi.example.lan"})  # each changes on its own
        self.assertEqual([c.name for c in book.boxes()], ["Lounge", "Living room again"])
        book.delete(other.id)
        self.assertEqual([c.id for c in book.boxes()], ["a1"])

    def test_refusals(self):
        self.write({"boxes": [{"host": "kodi.example.lan"}, {"host": "bedroom.example.lan"}]})
        book = self.book()
        for key, fields, kind in (
            ("gone.example.lan", {"host": "gone.example.lan"}, "can't save"),
            ("no-such-id", {"host": "kodi.example.lan"}, "can't save"),
            ("", {"host": "http://kodi.example.lan"}, "bad address"),
            ("", {"host": ""}, "bad address"),
            ("", {"host": "a.example.lan", "httpPort": "80a"}, "bad port"),
            ("", {"host": "a.example.lan", "tcpPort": 0}, "bad port"),
            ("", {"host": "a.example.lan", "mac": "Busy"}, "bad MAC address"),
            ("", {"host": "a.example.lan", "password": 5}, "bad password"),
        ):
            with self.assertRaises(OmakodiError, msg=fields) as cm:
                book.save(key, fields)
            self.assertEqual(cm.exception.kind, kind, fields)
        self.assertEqual(len(self.read()["boxes"]), 2)

    def test_a_broken_file_is_left_alone(self):
        self.write('{"host": "kodi.example.lan", ')
        with self.assertRaises(OmakodiError) as cm:
            self.book().save("", {"host": "a.example.lan"})
        self.assertEqual(cm.exception.kind, "can't save")
        with open(self.path) as f:
            self.assertEqual(f.read(), '{"host": "kodi.example.lan", ')

    def test_delete_and_use(self):
        self.write({"boxes": [{"name": "Living room", "host": "kodi.example.lan"},
                              {"name": "Bedroom", "host": "bedroom.example.lan"}]})
        book = self.book()
        self.assertEqual(book.current().name, "Living room")
        self.assertEqual(book.use("bedroom").host, "bedroom.example.lan")  # by name, any case
        self.assertEqual(book.current().name, "Bedroom")
        self.assertEqual(book.use("kodi.example.lan").name, "Living room")  # by address
        with self.assertRaises(OmakodiError) as cm:
            book.use("attic")
        self.assertEqual(cm.exception.kind, "no such box")
        book.use("Bedroom")
        book.delete("bedroom.example.lan")
        self.assertEqual(book.current().name, "Living room")  # the box in use went: the first
        with self.assertRaises(OmakodiError):
            book.delete("bedroom.example.lan")
        book.delete("kodi.example.lan")
        self.assertEqual(self.read(), {"boxes": []})
        self.assertEqual(book.boxes(), [])

    def test_box_list_has_no_passwords(self):
        self.write({"boxes": [{"name": "Living room", "host": "kodi.example.lan", "username": "kodi",
                               "password": SECRET, "mac": "02:00:00:00:00:01"},
                              {"host": "bedroom.example.lan"}]})
        macs = MacStore(self.state)
        macs.save("bedroom.example.lan", "02:00:00:00:00:02")
        book = self.book()
        listed = boxes.box_list(book.boxes(), book.current(), macs)
        self.assertEqual(listed, {"current": "kodi.example.lan", "list": [  # no ids yet: by host
            {"id": "kodi.example.lan", "name": "Living room", "host": "kodi.example.lan", "httpPort": 8080,
             "tcpPort": 9090, "username": "kodi", "hasPassword": True, "mac": "02:00:00:00:00:01", "knownMac": ""},
            {"id": "bedroom.example.lan", "name": "bedroom.example.lan", "host": "bedroom.example.lan",
             "httpPort": 8080, "tcpPort": 9090, "username": "", "hasPassword": False, "mac": "",
             "knownMac": "02:00:00:00:00:02"}]})
        self.assertNotIn(SECRET, json.dumps(listed))


class DiscoveryTest(unittest.TestCase):
    def test_parse(self):
        found = boxes.parse_avahi(AVAHI_HTTP)
        self.assertEqual([(s["name"], s["address"], s["port"]) for s in found], [
            ("Living room", "192.0.2.10", 8080), ("Living room", "192.0.2.10", 8080),
            ("Kodi (Bedroom)", "192.0.2.20", 8081)])
        self.assertEqual(found[0]["hostname"], "kodi.local")
        self.assertEqual(found[2]["uuid"], "22222222-aaaa-bbbb-cccc-000000000002")
        self.assertEqual(boxes.parse_avahi("junk\n=;;;\n" + "x;" * 50), [])

    def test_merge_and_leave_out_the_saved_ones(self):
        merged = boxes.merge_found(boxes.parse_avahi(AVAHI_HTTP), boxes.parse_avahi(AVAHI_TCP))
        self.assertEqual(merged, [
            {"name": "Kodi (Bedroom)", "host": "192.0.2.20", "hostname": "bedroom.local", "httpPort": 8081,
             "tcpPort": 9090},
            {"name": "Living room", "host": "192.0.2.10", "hostname": "kodi.local", "httpPort": 8080,
             "tcpPort": 9091}])
        saved = [config.Config("(test)", "KODI.local")]  # saved by its hostname
        self.assertEqual(boxes.new_boxes(merged, saved), [
            {"name": "Kodi (Bedroom)", "host": "192.0.2.20", "httpPort": 8081, "tcpPort": 9090}])
        saved = [config.Config("(test)", "192.0.2.20", http_port=8080)]  # another port: another Kodi
        self.assertEqual(len(boxes.new_boxes(merged, saved)), 2)

    def test_discover(self):
        asked = []

        def browse(service, timeout):
            asked.append(service)
            return AVAHI_HTTP if service == boxes.HTTP_SERVICE else AVAHI_TCP

        self.assertEqual(len(boxes.discover(browse)), 2)
        self.assertEqual(sorted(asked), sorted([boxes.HTTP_SERVICE, boxes.TCP_SERVICE]))

        def failing(service, timeout):
            raise OmakodiError("can't search the network", "avahi-browse isn't installed (the avahi package)")

        with self.assertRaises(OmakodiError) as cm:
            boxes.discover(failing)
        self.assertIn("avahi", str(cm.exception))

        def no_tcp(service, timeout):  # the live port is then Kodi's default
            if service == boxes.TCP_SERVICE:
                raise OmakodiError("can't search the network", "x")
            return AVAHI_HTTP
        self.assertEqual({b["tcpPort"] for b in boxes.discover(no_tcp)}, {9090})


class TestConnectionTest(unittest.TestCase):
    def setUp(self):
        self.fake = FakeKodi(password=SECRET).start()
        self.fake.results["Application.GetProperties"] = {"name": "Kodi", "version": {"major": 21, "minor": 3}}
        self.fake.results["XBMC.GetInfoLabels"] = {"System.FriendlyName": "Living room",
                                                   "Network.MacAddress": "02:00:00:00:00:05"}
        self.fields = {"host": "127.0.0.1", "httpPort": self.fake.http_port, "tcpPort": self.fake.tcp_port,
                       "username": "kodi"}

    def tearDown(self):
        self.fake.stop()

    def test_with_the_typed_or_the_saved_password(self):
        want = {"message": "✓ Kodi 21.3", "name": "Living room", "mac": "02:00:00:00:00:05"}
        self.assertEqual(boxes.test_box({**self.fields, "password": SECRET}), want)
        self.assertEqual(boxes.test_box(self.fields, password=SECRET), want)  # the field untouched
        with self.assertRaises(OmakodiError) as cm:  # typed wins over the saved one
            boxes.test_box({**self.fields, "password": "wrong"}, password=SECRET)
        self.assertEqual(cm.exception.kind, "wrong username or password")
        self.assertNotIn(SECRET, str(cm.exception))
        self.assertIn("this box's settings", str(cm.exception))

    def test_a_box_that_isnt_there(self):
        self.fake.stop()
        with self.assertRaises(OmakodiError) as cm:
            boxes.test_box(self.fields)
        self.assertEqual(cm.exception.kind, "not reachable")


class PerBoxStateTest(unittest.TestCase):
    def test_youtube_failures_and_stops_are_per_box(self):
        with tempfile.TemporaryDirectory() as d:
            now = [1000.0]
            a = YoutubeHealth(d, now=lambda: now[0], box="kodi.example.lan")
            b = a.for_box("bedroom.example.lan")
            a.record_failure()
            self.assertTrue(a.failed_recently())
            self.assertFalse(b.failed_recently())
            b.record_failure()
            a.clear()
            self.assertFalse(a.failed_recently())
            self.assertTrue(b.failed_recently())

            stops = StopNote(d, now=lambda: now[0])
            stops.record("kodi.example.lan")
            self.assertTrue(stops.since(999, "kodi.example.lan"))
            self.assertFalse(stops.since(999, "bedroom.example.lan"))  # a stop on another box
            self.assertTrue(stops.since(999))
            with open(stops.path, "w") as f:  # omakodi 0.2's note: any box
                f.write("1000.000\n")
            self.assertTrue(stops.since(999, "bedroom.example.lan"))


class TwoBoxDaemonTest(unittest.TestCase):
    """The daemon with two fake Kodis in a list config: it follows the box
    in use, and switching reads the other box's state."""

    def setUp(self):
        self.a = FakeKodi(password=SECRET).start()
        self.b = FakeKodi(username="", password="").start()
        for fake, volume in ((self.a, 30), (self.b, 70)):
            fake.results["Application.GetProperties"] = {"volume": volume, "muted": False, "name": "Kodi",
                                                         "version": {"major": 21, "minor": 3}}
            fake.results["Player.GetActivePlayers"] = []
            fake.results["System.GetProperties"] = {"canreboot": False, "canshutdown": False}
            fake.results["XBMC.GetInfoLabels"] = {"Network.MacAddress": "Busy", "System.FriendlyName": "Bedroom"}
        self.tmp = tempfile.TemporaryDirectory()
        self.state = os.path.join(self.tmp.name, "state")
        self.path = os.path.join(self.tmp.name, "config.json")
        with open(self.path, "w") as f:
            json.dump({"boxes": [
                {"id": "a1", "name": "Living room", "host": "127.0.0.1", "httpPort": self.a.http_port,
                 "tcpPort": self.a.tcp_port, "username": "kodi", "password": SECRET},
                {"id": "b2", "name": "Bedroom", "host": "localhost", "httpPort": self.b.http_port,
                 "tcpPort": self.b.tcp_port},
            ]}, f)
        os.chmod(self.path, 0o600)
        self.chosen = ChosenBox(self.state)
        self.found_calls = []
        self.d = daemon.Daemon(
            daemon.ConfigWatcher(self.path, self.chosen), book=boxes.BoxBook(self.path, self.chosen),
            macs=MacStore(self.state), volume_keys=HostValue("volume", "keys", daemon.VOLUME_KEYS, self.state),
            stops=StopNote(self.state), youtube_modes=mode_store(self.state), health=YoutubeHealth(self.state),
            art_cache=ArtCache(os.path.join(self.state, "art")), titles=TitleStore(self.state),
            shortcuts=ShortcutStore(self.state), discover=self.fake_discover)
        in_r, self.in_w = os.pipe()
        out_r, out_w = os.pipe()
        self.inp = os.fdopen(in_r, "rb")
        self.out = os.fdopen(out_w, "wb")
        self.lines = Lines(os.fdopen(out_r, "rb"))
        self.thread = threading.Thread(target=self.d.run, args=(self.inp, self.out), daemon=True)
        self.thread.start()

    def fake_discover(self):
        self.found_calls.append(1)
        return [{"name": "Bedroom", "host": "localhost", "hostname": "", "httpPort": self.b.http_port,
                 "tcpPort": 9090},
                {"name": "Attic", "host": "192.0.2.30", "hostname": "attic.local", "httpPort": 8080, "tcpPort": 9090}]

    def tearDown(self):
        os.close(self.in_w)
        self.thread.join(2)
        self.inp.close()
        self.out.close()
        self.lines.close()
        self.a.stop()
        self.b.stop()
        self.tmp.cleanup()
        for line in self.lines.raw:
            self.assertNotIn(SECRET.encode(), line)
            self.assertNotIn(OTHER_SECRET.encode(), line)

    def send(self, obj):
        os.write(self.in_w, json.dumps(obj).encode() + b"\n")

    def wait_for(self, test, kind="state", timeout=5.0):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            try:
                msg = self.lines.next(0.3)
            except AssertionError:
                continue
            if msg and msg.get("type") == kind and test(msg):
                return msg
        self.fail(f"no such {kind}")

    def test_switching_boxes_and_back(self):
        first = self.wait_for(lambda m: m["reachable"])
        self.assertEqual((first["volume"], first["boxes"]["current"], first["connecting"]), (30, "a1", False))
        self.assertEqual([b["name"] for b in first["boxes"]["list"]], ["Living room", "Bedroom"])
        self.assertEqual([b["hasPassword"] for b in first["boxes"]["list"]], [True, False])
        self.assertTrue(self.a.wait_for_event_client())
        self.send({"id": 1, "cmd": "youtubeMode", "mode": "sendtokodi-only"})  # for the living room only
        self.assertTrue(self.lines.result(1)["ok"])

        self.send({"id": 2, "cmd": "box", "key": "b2"})
        self.assertEqual(self.lines.result(2)["message"], "Switched to Bedroom")
        switching = self.wait_for(lambda m: m["boxes"]["current"] == "b2")
        self.assertTrue(switching["connecting"])  # nothing of the living room's state stands
        self.assertEqual((switching["reachable"], switching["volume"], switching["playing"]), (False, None, None))
        state = self.wait_for(lambda m: m["reachable"] and m["volume"] == 70)
        self.assertFalse(state["connecting"])
        self.assertEqual(state["youtube"], {"mode": "smart", "from": "config", "avoidUntil": 0, "box": "b2"})
        self.assertEqual(state["shortcuts"]["box"], "b2")
        self.assertTrue(self.b.wait_for_event_client())  # the event port follows the box
        deadline = time.monotonic() + 3
        while not self.a.closed_by_client and time.monotonic() < deadline:
            time.sleep(0.05)
        self.assertEqual(self.a.closed_by_client, 1)  # the living room's event port is closed
        self.assertEqual(self.chosen.read(), "b2")

        # Keys go to the box in use.
        self.a.clear_calls()
        self.b.results["XBMC.GetInfoBooleans"] = {}
        self.send({"id": 3, "cmd": "control", "action": "home"})
        self.assertTrue(self.lines.result(3)["ok"])
        self.assertIn("GUI.ActivateWindow", self.b.methods())
        self.assertNotIn("GUI.ActivateWindow", self.a.methods())

        # And back, from the CLI's way: box.json changes under the daemon.
        self.chosen.save("a1")
        state = self.wait_for(lambda m: m["reachable"] and m["boxes"]["current"] == "a1" and m["volume"] == 30)
        self.assertEqual(state["youtube"]["mode"], "sendtokodi-only")  # the living room's own choice

        self.send({"id": 4, "cmd": "box", "key": "attic.example.lan"})
        self.assertIn("no such box", self.lines.result(4)["error"])

    def test_an_unreachable_box_says_so_at_once(self):
        self.wait_for(lambda m: m["reachable"])
        self.b.stop()
        self.send({"id": 1, "cmd": "box", "host": "Bedroom"})
        self.lines.result(1)
        state = self.wait_for(lambda m: not m["connecting"] and m["boxes"]["current"] == "b2", timeout=8)
        self.assertFalse(state["reachable"])  # no 45 s grace for the box switched to
        self.assertTrue(state["error"].startswith("Can't reach "), state["error"])

    def test_switching_away_from_a_box_that_is_off(self):
        self.wait_for(lambda m: m["reachable"])
        self.a.results["System.GetProperties"] = {"canreboot": True, "canshutdown": True}
        self.d._power_caps = None
        self.send({"id": 1, "cmd": "refresh"})
        self.lines.result(1)
        self.send({"id": 2, "cmd": "control", "action": "shutdown"})
        self.assertTrue(self.lines.result(2)["ok"])
        self.wait_for(lambda m: (m["power"] or {}).get("state") == "off")
        self.send({"id": 3, "cmd": "box", "host": "localhost"})  # a remote older than ids
        state = self.wait_for(lambda m: m["reachable"] and m["boxes"]["current"] == "b2")
        self.assertEqual((state["volume"], state["power"]["state"]), (70, "on"))  # not the living room's "off"

    def test_saving_testing_and_deleting(self):
        self.wait_for(lambda m: m["reachable"])
        # Test connection with the saved password (the field untouched).
        self.send({"id": 1, "cmd": "boxTest", "key": "a1",
                   "box": {"host": "127.0.0.1", "httpPort": self.a.http_port, "username": "kodi"}})
        tested = self.wait_for(lambda m: m["id"] == 1, kind="boxTest")
        self.assertEqual(tested, {"type": "boxTest", "id": 1, "name": "Bedroom", "mac": ""})
        self.assertEqual(self.lines.result(1), {"type": "result", "id": 1, "ok": True, "message": "✓ Kodi 21.3"})
        # A new box gets no saved password, even at the same address.
        self.send({"id": 2, "cmd": "boxTest", "key": "",
                   "box": {"host": "127.0.0.1", "httpPort": self.a.http_port, "username": "kodi"}})
        self.assertIn("wrong username or password", self.lines.result(2)["error"])

        self.send({"id": 3, "cmd": "boxSave", "key": "",
                   "box": {"name": "Attic", "host": "192.0.2.30", "httpPort": 8080, "tcpPort": 9090,
                           "username": "kodi", "password": OTHER_SECRET, "mac": ""}})
        self.assertEqual(self.lines.result(3)["message"], "Saved Attic")
        state = self.wait_for(lambda m: len(m["boxes"]["list"]) == 3)
        attic = state["boxes"]["list"][2]
        self.assertEqual((attic["name"], state["boxes"]["current"]), ("Attic", attic["id"]))
        self.assertNotIn(attic["id"], ("a1", "b2", "192.0.2.30"))  # a new id of its own
        self.send({"id": 4, "cmd": "box", "key": "a1"})
        self.lines.result(4)
        self.send({"id": 5, "cmd": "boxDelete", "key": attic["id"]})
        self.assertEqual(self.lines.result(5)["message"], "Deleted")
        self.wait_for(lambda m: len(m["boxes"]["list"]) == 2)
        for bad in ({"id": 6, "cmd": "boxSave", "box": {"host": "x", "secret": 1}},
                    {"id": 6, "cmd": "boxSave", "key": 5, "box": {"host": "x"}},
                    {"id": 6, "cmd": "boxDelete"}, {"id": 6, "cmd": "box", "key": ""}, {"id": 6, "cmd": "box", "key": 5}):
            self.send(bad)
            self.assertIn("bad request", self.lines.result(6)["error"])

    def test_found_on_your_network(self):
        self.wait_for(lambda m: m["reachable"])
        self.send({"id": 1, "cmd": "discover"})
        self.assertEqual(self.wait_for(lambda m: True, kind="found")["status"], "searching")
        found = self.wait_for(lambda m: m["status"] == "done", kind="found")
        # The bedroom is saved already: only the attic is new.
        self.assertEqual(found, {"type": "found", "status": "done", "error": "", "total": 2, "boxes": [
            {"name": "Attic", "host": "192.0.2.30", "httpPort": 8080, "tcpPort": 9090}]})
        self.assertTrue(self.lines.result(1)["ok"])
        self.send({"id": 2, "cmd": "boxSave", "key": "", "box": {"name": "Attic", "host": "192.0.2.30"}})
        self.assertEqual(self.wait_for(lambda m: True, kind="found")["boxes"], [])  # added: not new any more
        self.assertTrue(self.lines.result(2)["ok"])


class BoxCliTest(Files):
    def run_cli(self, *args):
        env = {**os.environ, "OMAKODI_CONFIG": self.path, "XDG_STATE_HOME": self.state}
        return subprocess.run([sys.executable, "-I", os.path.join(ROOT, "bin", "omakodi"), *args],
                              capture_output=True, text=True, env=env, timeout=20)

    def test_box_and_boxes(self):
        self.write({"boxes": [{"name": "Living room", "host": "kodi.example.lan", "password": SECRET},
                              {"name": "Bedroom", "host": "bedroom.example.lan"}]})
        out = self.run_cli("boxes")
        self.assertEqual(out.stdout, "* Living room  (kodi.example.lan:8080)\n  Bedroom  (bedroom.example.lan:8080)\n")
        self.assertEqual(self.run_cli("box", "bedroom").stdout, "Switched to Bedroom (bedroom.example.lan).\n")
        self.assertEqual(self.run_cli("box").stdout, "Bedroom\n")
        shown = json.loads(self.run_cli("config").stdout)
        self.assertEqual((shown["host"], shown["boxes"]), ("bedroom.example.lan", ["Living room", "Bedroom"]))
        bad = self.run_cli("box", "attic")
        self.assertEqual(bad.returncode, 2)
        self.assertIn("no such box", bad.stderr)
        for out in (self.run_cli("boxes"), self.run_cli("config")):
            self.assertNotIn(SECRET, out.stdout + out.stderr)


if __name__ == "__main__":
    unittest.main()


try:
    import shutil
    from test_protocol_js import EvalJs
except ImportError:  # pragma: no cover
    EvalJs = None


@unittest.skipUnless(shutil.which("node"), "node is needed to run Boxes.js")
class EditorChecksTest(EvalJs, unittest.TestCase):
    """Boxes.js lets Save send exactly what editor_box() takes."""

    HOSTS = ["kodi.example.lan", " kodi.example.lan ", "192.0.2.10", "fe80::1", "", " ", "http://kodi",
             "kodi:8080", "kodi example", "kodi/x", "user@kodi", "kodi\n", "　kodi\x85", "ködi",
             "a" * 253, "a" * 254, "﻿kodi"]
    PORTS = ["", " ", "8080", " 8080 ", "0", "1", "65535", "65536", "080", "8o80", "-1", "1e3", "²", "١",
             "123456", "8080\n"]
    MACS = ["", " ", "02:00:00:00:00:01", "02-00-00-00-00-01", "02:00-00:00:00:01", "03:00:00:00:00:01",
            "00:00:00:00:00:00", "AA:BB:CC:DD:EE:FE", "aa:bb:cc:dd:ee", "Busy", " 02:00:00:00:00:0a "]

    def python(self, form):
        """What editor_box() makes of the fields: the error's kind, or
        [host, web port, live port, mac]."""
        try:
            box = boxes.editor_box(form, {})
        except OmakodiError as e:
            return e.kind
        return [box["host"], box["httpPort"], box["tcpPort"], box.get("mac", "")]

    def test_the_same_as_the_daemon(self):
        forms = ([{"host": h} for h in self.HOSTS]
                 + [{"host": "kodi.example.lan", "httpPort": p} for p in self.PORTS]
                 + [{"host": "kodi.example.lan", "tcpPort": p} for p in self.PORTS]
                 + [{"host": "kodi.example.lan", "mac": m} for m in self.MACS])
        expr = ("%s.map(function(f) { var p = problem(f); if (p) return p; var b = fields(f);"
                " return [host(f.host), b.httpPort, b.tcpPort, mac(f.mac)] })") % json.dumps(forms)
        kinds = {"address": "bad address", "webPort": "bad port", "livePort": "bad port", "mac": "bad MAC address"}
        for form, js in zip(forms, self.js("Boxes.js", expr)):
            self.assertEqual(kinds.get(js, js) if isinstance(js, str) else js, self.python(form), form)

    def test_the_password_only_when_typed(self):
        got = self.js("Boxes.js", "[fields({host: 'k', password: 'x', passwordEdited: false}),"
                                  " fields({host: 'k', password: '', passwordEdited: true})]")
        self.assertNotIn("password", got[0])
        self.assertEqual(got[1]["password"], "")


@unittest.skipUnless(shutil.which("node"), "node is needed to run the JS files")
class ShellSideTest(EvalJs, unittest.TestCase):
    """Protocol.js takes the boxes from the daemon's lines; b opens the page."""

    def test_state_found_and_test_lines(self):
        state = {"type": "state", "connecting": True, "boxes": {"current": "a1", "list": [
            {"id": "a1", "name": "Living room", "host": "kodi.example.lan", "httpPort": 8080, "tcpPort": 9090,
             "username": "kodi", "hasPassword": True, "mac": "02:00:00:00:00:01", "knownMac": "x",
             "password": SECRET},
            {"id": "b2", "host": "bedroom.example.lan", "httpPort": 0}, {"id": "c3", "name": "no host"},
            {"name": "no id", "host": "old.example.lan"}, {"id": 5, "host": "x.example.lan"}, "junk"]}}
        found = {"type": "found", "status": "done", "total": 3, "error": "",
                 "boxes": [{"name": "Attic", "host": "192.0.2.30", "httpPort": 8080, "tcpPort": 9090}, {}]}
        expr = "[%s].map(function(m) { return parse(JSON.stringify(m)) })" % ", ".join(
            json.dumps(m) for m in (state, found, {"type": "boxTest", "id": 4, "name": "Attic", "mac": "nope"},
                                    {"type": "state"}))
        got = self.js("Protocol.js", expr)
        self.assertTrue(got[0]["connecting"])
        self.assertEqual(got[0]["boxes"], {"current": "a1", "list": [  # each by its id
            {"id": "a1", "name": "Living room", "host": "kodi.example.lan", "httpPort": 8080, "tcpPort": 9090,
             "username": "kodi", "hasPassword": True, "mac": "02:00:00:00:00:01", "knownMac": ""},
            {"id": "b2", "name": "bedroom.example.lan", "host": "bedroom.example.lan", "httpPort": 8080,
             "tcpPort": 9090, "username": "", "hasPassword": False, "mac": "", "knownMac": ""}]})
        self.assertNotIn(SECRET, json.dumps(got))
        self.assertEqual(got[1], {"type": "found", "status": "done", "error": "", "total": 3, "boxes": [
            {"name": "Attic", "host": "192.0.2.30", "httpPort": 8080, "tcpPort": 9090}]})
        self.assertEqual(got[2], {"type": "boxTest", "id": 4, "name": "Attic", "mac": ""})
        self.assertEqual((got[3]["boxes"], got[3]["connecting"]), ({"current": "", "list": []}, False))

    def test_b_opens_the_boxes(self):
        self.assertEqual(self.js("RemoteKeys.js", '[lookup(0, "b", 0), lookup(0, "b", 0x04000000)]'),
                         [{"boxes": True}, None])
