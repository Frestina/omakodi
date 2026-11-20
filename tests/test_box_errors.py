"""A box's address, MAC and Test connection errors like the phone remote (ticket 057).

A config whose "mac" isn't a MAC address loads (the box works, waking says
"Invalid MAC address for <box>"), and a valid config loads exactly as
before. The box editor refuses an address that can't be one, with the same
check as rpc.is_address, in Python and in Boxes.js alike. Test connection's
errors are the phone remote's words, naming the box by the editor's Name,
else its address, and never hold the password.
"""

import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fakekodi import ROOT, FakeKodi  # noqa: E402
from test_protocol_js import EvalJs  # noqa: E402
from omakodi import boxes, boxids, config, messages, wol  # noqa: E402
from omakodi.errors import OmakodiError  # noqa: E402
from omakodi.rpc import is_address  # noqa: E402
from omakodi.state import ChosenBox  # noqa: E402

SECRET = "s3cret-example-pw"
MAC = "02:1a:2b:3c:4d:5e"


class Files(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "config", "config.json")
        self.state = os.path.join(self.tmp.name, "state")

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, data):
        os.makedirs(os.path.dirname(self.path), mode=0o700, exist_ok=True)
        with open(self.path, "w") as f:
            json.dump(data, f, indent=2)
        os.chmod(self.path, 0o600)

    def raw(self):
        with open(self.path, "rb") as f:
            return f.read()


class BadMacTest(Files):
    """A "mac" that isn't one no longer breaks the whole config."""

    def boxes(self, mac):
        return {"boxes": [{"id": "a1", "name": "Living room", "host": "kodi.example.lan", "username": "kodi",
                           "password": SECRET, "mac": mac},
                          {"id": "b2", "name": "Bedroom", "host": "bedroom.example.lan"}]}

    def test_the_box_loads_and_waking_says_so(self):
        for mac in ("Busy", "ff:ff:ff:ff:ff:ff", "00:00:00:00:00:00", "01:00:5e:00:00:01", "aa:bb:cc:dd:ee",
                    " ", "x" * 1024):
            with self.subTest(mac=mac[:20]):
                self.write(self.boxes(mac))
                living, bedroom = config.load_all(self.path)
                self.assertEqual((living.host, living.password, living.mac, living.mac_ok),
                                 ("kodi.example.lan", SECRET, mac, False))
                self.assertEqual(bedroom.mac, "")
                self.assertEqual(living.public()["mac"], f"{mac} (not a MAC address)")
                store = wol.MacStore(self.state)
                store.save("a1", MAC)  # the config's wins, as on the phone remote
                sent = []
                with self.assertRaises(OmakodiError) as cm:
                    wol.wake(living, store, send=sent.append)
                self.assertEqual((str(cm.exception), cm.exception.code), ("Invalid MAC address for Living room", 1))
                self.assertEqual(messages.for_user(cm.exception), "Invalid MAC address for Living room")
                self.assertEqual(sent, [])

    def test_a_mac_that_isnt_text_is_still_a_bad_config(self):
        for mac in (5, None, ["aa"], True, "x" * 1025):
            with self.subTest(mac=mac if not isinstance(mac, str) else "long"):
                self.write(self.boxes(mac))
                with self.assertRaises(OmakodiError) as cm:
                    config.load_all(self.path)
                self.assertEqual(cm.exception.kind, "bad config")
                self.assertNotIn(SECRET, str(cm.exception))

    def test_a_valid_config_loads_as_before_and_is_not_written(self):
        # As the user's: ids, a password, a MAC in either form, wakeOnLan.
        self.write({"youtubeMode": "smart", "boxes": [
            {"id": "a1", "name": "Living room", "host": "192.0.2.10", "username": "kodi", "password": SECRET,
             "mac": "02-1A-2B-3C-4D-5E"},
            {"id": "b2", "name": "Bedroom", "host": "bedroom.example.lan", "wakeOnLan": False}]})
        before, mtime = self.raw(), os.stat(self.path).st_mtime_ns
        living, bedroom = config.load_all(self.path)
        self.assertEqual((living.mac, living.mac_ok, living.public()["mac"]), (MAC, True, MAC))
        self.assertEqual((bedroom.mac, bedroom.public()["mac"], bedroom.wake_on_lan), ("", "not set", False))
        self.assertFalse(boxids.migrate(self.path, self.state))
        self.assertEqual((self.raw(), os.stat(self.path).st_mtime_ns), (before, mtime))
        self.assertEqual(wol.mac_for(living, wol.MacStore(self.state)), MAC)

    def test_the_single_box_form_too(self):
        self.write({"host": "kodi.example.lan", "mac": "Busy"})
        cfg = config.load(self.path, chosen="")
        self.assertEqual((cfg.host, cfg.mac), ("kodi.example.lan", "Busy"))

    def test_the_move_to_ids_and_saving_keep_it_as_written(self):
        self.write({"boxes": [{"name": "Living room", "host": "kodi.example.lan", "mac": "Busy"}]})
        self.assertTrue(boxids.migrate(self.path, self.state))
        moved = json.loads(self.raw())["boxes"][0]
        self.assertEqual(moved["mac"], "Busy")
        self.assertTrue(moved["id"])
        book = boxes.BoxBook(self.path, ChosenBox(self.state))
        book.save("", {"name": "Bedroom", "host": "bedroom.example.lan"})  # another box: this one stays
        self.assertEqual(json.loads(self.raw())["boxes"][0]["mac"], "Busy")
        listed = boxes.box_list(book.boxes(), book.boxes()[0])["list"][0]
        self.assertEqual((listed["mac"], listed["knownMac"]), ("Busy", ""))  # the editor shows it

    def test_the_editor_still_refuses_one(self):
        self.write({"boxes": [{"id": "a1", "name": "Living room", "host": "kodi.example.lan", "mac": "Busy"}]})
        book = boxes.BoxBook(self.path, ChosenBox(self.state))
        before = self.raw()
        with self.assertRaises(OmakodiError) as cm:
            book.save("a1", {"name": "Living room", "host": "kodi.example.lan", "mac": "Busy"})
        self.assertEqual(cm.exception.kind, "bad MAC address")
        self.assertEqual(self.raw(), before)
        book.save("a1", {"name": "Living room", "host": "kodi.example.lan", "mac": ""})  # emptied: Kodi's
        self.assertNotIn("mac", json.loads(self.raw())["boxes"][0])

    def test_omakodi_wake_says_it(self):
        self.write({"boxes": [{"id": "a1", "name": "Living room", "host": "kodi.example.lan", "mac": "Busy"}]})
        env = {k: v for k, v in os.environ.items() if not k.startswith(("OMAKODI_", "XDG_"))}
        env.update(HOME=self.tmp.name, OMAKODI_CONFIG=self.path, XDG_STATE_HOME=self.state,
                   XDG_CONFIG_HOME=os.path.join(self.tmp.name, "config"))
        p = subprocess.run([os.path.join(ROOT, "bin", "omakodi"), "wake"], capture_output=True, text=True,
                           env=env, timeout=10)
        self.assertEqual((p.returncode, p.stderr), (1, "omakodi: Invalid MAC address for Living room\n"))
        shown = subprocess.run([os.path.join(ROOT, "bin", "omakodi"), "config"], capture_output=True, text=True,
                               env=env, timeout=10)
        self.assertEqual(shown.returncode, 0, shown.stderr)
        self.assertEqual(json.loads(shown.stdout)["mac"], "Busy (not a MAC address)")


# Addresses the editor takes, and ones it can't: kodi..lan, a port, a scheme.
GOOD = ["kodi.example.lan", " kodi.example.lan ", "kodi", "kodi.example.lan.", "media_box", "192.0.2.10",
        "1.2.3.256", "01.2.3.4", "2001:db8::10", "::1", "::", "fe80::1", "1:2:3:4:5:6:7:8", "1::", "::ffff:1.2.3.4",
        "1:2:3:4:5:6:1.2.3.4", "1:2:3:4:5:6:7::", "::2:3:4:5:6:7:8", "a" * 63 + ".lan", "x-1.example.lan",
        ".".join(["a" * 63] * 3) + "." + "a" * 61, "ABCD:EF01::1"]
BAD = ["", " ", "kodi..lan", ".kodi", "kodi.lan..", ".", "kodi.example.lan:8080", "192.0.2.10:8080", "-kodi",
       "kodi-", "kodi.-x.lan", "a" * 64 + ".lan", ".".join(["a" * 63] * 4), "http://kodi", "kodi/x", "user@kodi",
       "kodi example", "ködi", "1:2", ":::", "1:::2", "1::2::3", "12345::1", "1:2:3:4:5:6:7:8:9", "1:2:3:4:5:6:7",
       "::1.2.3.04", "::1.2.3", "::256.1.1.1", "1:2:3:4:5:6:7:1.2.3.4", ":1::2", "1::2:", "1:2:3:4:5:6:7:8::",
       "g::1", "1" * 40 + "::1", "kodi\x00", "fe80::1%eth0"]


class EditorAddressTest(EvalJs, unittest.TestCase):
    """The editor refuses an address that can't be one, in Python and Boxes.js alike."""

    def test_python(self):
        for host in GOOD:
            with self.subTest(host):
                self.assertEqual(boxes.editor_box({"host": host}, {})["host"], host.strip())
        for host in BAD:
            with self.subTest(host):
                with self.assertRaises(OmakodiError) as cm:
                    boxes.editor_box({"host": host}, {})
                self.assertEqual(cm.exception.kind, "bad address")

    def test_saved_and_tested_boxes_alike(self):
        # Test connection refuses it too, without asking anything: the phone remote's words.
        for host in ("kodi..lan", "kodi.example.lan:8080"):
            for name, box in (("Attic", "Attic"), ("", host)):
                with self.subTest(host=host, name=name):
                    with self.assertRaises(OmakodiError) as cm:
                        boxes.test_box({"name": name, "host": host, "password": SECRET})
                    self.assertEqual(messages.for_user(cm.exception), f"Bad address for {box}")

    def corpus(self):
        rng = random.Random(57)
        alphabet = "0123456789abcdefABCDEFg:._-"
        texts = GOOD + BAD + [" " + h + "\t" for h in GOOD[:5]]
        for _ in range(4000):
            texts.append("".join(rng.choice(alphabet) for _ in range(rng.randint(1, 24))))
        for _ in range(1500):  # IPv6-like: hextets, "::", an IPv4 end
            parts = [rng.choice(["", "0", "1", "ab", "ffff", "Db8"] * 4 + ["12345", "g", "1.2.3.4", "300.1.1.1",
                                                                          "01.1.1.1"])
                     for _ in range(rng.randint(2, 10))]
            texts.append(":".join(parts))
            if rng.random() < 0.5:  # one "::" somewhere
                at = rng.randint(0, len(parts))
                texts.append(":".join(p for p in parts[:at] if p) + "::" + ":".join(p for p in parts[at:] if p))
        return texts

    @unittest.skipUnless(shutil.which("node"), "node is needed to run Boxes.js")
    def test_boxes_js_is_the_same(self):
        texts = self.corpus()
        got = self.js("Boxes.js", "%s.map(function(h) { return [host(h), isAddress(h)] })" % json.dumps(texts))
        for text, (host, address) in zip(texts, got):
            self.assertEqual(host, boxes.editor_host(text), repr(text))
            if config.HOST_RE.fullmatch(text):  # the texts the config takes at all
                self.assertEqual(address, is_address(text), repr(text))
        self.assertEqual(self.js("Boxes.js", '["kodi..lan", "kodi.example.lan:8080", "kodi.example.lan"]'
                                             '.map(function(h) { return problem({host: h}) })'),
                         ["address", "address", ""])


@unittest.skipUnless(shutil.which("node"), "node is needed to run Protocol.js")
class ShellSideTest(EvalJs, unittest.TestCase):
    def test_the_editor_gets_the_configs_mac_as_written(self):
        state = {"type": "state", "boxes": {"current": "a1", "list": [
            {"id": "a1", "host": "kodi.example.lan", "mac": "Busy", "knownMac": "Busy"},
            {"id": "b2", "host": "bedroom.example.lan", "mac": MAC, "knownMac": MAC},
            {"id": "c3", "host": "attic.example.lan", "mac": 5}]}}
        got = self.js("Protocol.js", "parse(%s).boxes.list.map(function(b) { return [b.mac, b.knownMac] })"
                      % json.dumps(json.dumps(state)))
        self.assertEqual(got, [["Busy", ""], [MAC, MAC], ["", ""]])  # what Kodi told stays checked


class TestConnectionWordsTest(unittest.TestCase):
    """Test connection's errors in the phone remote's words, with the box's
    name where it has one, else its address."""

    def setUp(self):
        self.fake = FakeKodi(password=SECRET).start()
        self.fake.results["Application.GetProperties"] = {"name": "Kodi", "version": {"major": 21, "minor": 3}}
        self.fields = {"name": "Living room", "host": "127.0.0.1", "httpPort": self.fake.http_port,
                       "tcpPort": self.fake.tcp_port, "username": "kodi", "password": SECRET}

    def tearDown(self):
        self.fake.stop()

    def said(self, **fields):
        with self.assertRaises(OmakodiError) as cm:
            boxes.test_box({**self.fields, **fields})
        said = messages.for_user(cm.exception)
        self.assertNotIn(SECRET, said + messages.with_fix(cm.exception) + str(cm.exception))
        return said

    def test_ok_stays(self):
        self.assertEqual(boxes.test_box(self.fields)["message"], "✓ Kodi 21.3")

    def test_wrong_password(self):
        self.assertEqual(self.said(password="wrong"), "Wrong username or password for Living room")
        self.assertEqual(self.said(password="wrong", name=""), "Wrong username or password for 127.0.0.1")
        self.assertEqual(self.said(password="wrong", name="  "), "Wrong username or password for 127.0.0.1")

    def test_another_http_status(self):
        self.fake.http_status = 503
        self.assertEqual(self.said(), "Living room answered HTTP 503")

    def test_an_unexpected_reply(self):
        self.fake.raw_reply = b"<html>hello</html>"
        self.assertEqual(self.said(), "Unexpected reply from Living room")

    def test_nothing_there(self):
        self.fake.stop()
        self.assertEqual(self.said(), "Can't reach Living room")

    def test_a_name_that_doesnt_resolve(self):
        self.assertEqual(self.said(host="no-such-host.invalid", name=""), "Can't reach no-such-host.invalid")


if __name__ == "__main__":
    unittest.main()
