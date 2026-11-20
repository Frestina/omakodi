"""Kodi boxes known by an id (ticket 054): the move from host-keyed config
and state files (omakodi 0.2's one box and 042's list), two boxes on one
address, an address change keeping a box's settings, and delete clearing
them. Everything runs on fictional files in a temporary folder."""

import json
import os
import stat
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import fakekodi  # noqa: E402,F401  (puts lib/ on the path)
from omakodi import boxes, boxids, config, daemon  # noqa: E402
from omakodi.shortcuts import Shortcut, ShortcutStore  # noqa: E402
from omakodi.art import ArtCache  # noqa: E402
from omakodi.state import ChosenBox, HostValue, StopNote, YoutubeHealth  # noqa: E402
from omakodi.titles import TitleStore  # noqa: E402
from omakodi.wol import MacStore  # noqa: E402
from omakodi.youtubemode import mode_store, youtube_mode  # noqa: E402

SECRET = "s3cret-example-pw"
OTHER_SECRET = "an0ther-example-pw"
MAC_A = "02:00:00:00:00:0a"
MAC_B = "02:00:00:00:00:0b"
UUID_RE = r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
MOVIES = Shortcut(label="Films", window="videos", path="videodb://movies/titles/")
ADDON = Shortcut(label="Trending", path="plugin://plugin.video.example/trending/")


class Folder(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "config", "omakodi", "config.json")
        self.state = os.path.join(self.tmp.name, "state", "omakodi")
        os.makedirs(os.path.dirname(self.path), mode=0o700)
        os.makedirs(self.state, mode=0o700)

    def tearDown(self):
        for d, _, _ in os.walk(self.tmp.name):
            os.chmod(d, 0o700)
        self.tmp.cleanup()

    def write(self, data, mode=0o600):
        with open(self.path, "w") as f:
            f.write(data if isinstance(data, str) else json.dumps(data, indent=4))
        os.chmod(self.path, mode)

    def read(self):
        with open(self.path) as f:
            return json.load(f)

    def put(self, name, data):
        with open(os.path.join(self.state, name), "w") as f:
            json.dump(data, f)
        os.chmod(os.path.join(self.state, name), 0o600)

    def get(self, name):
        with open(os.path.join(self.state, name)) as f:
            return json.load(f)

    def snapshot(self):
        """Every file's bytes and mode, under the temporary folder (the
        empty lock file aside)."""
        files = {}
        for d, _, names in os.walk(self.tmp.name):
            for n in names:
                if n == boxids.LOCK:
                    continue
                p = os.path.join(d, n)
                with open(p, "rb") as f:
                    files[os.path.relpath(p, self.tmp.name)] = (f.read(), stat.S_IMODE(os.stat(p).st_mode))
        return files

    def stores(self):
        return {"macs": MacStore(self.state), "volume": HostValue("volume", "keys", daemon.VOLUME_KEYS, self.state),
                "modes": mode_store(self.state), "health": YoutubeHealth(self.state, now=lambda: 2000.0),
                "shortcuts": ShortcutStore(self.state)}

    def settings(self, cfg):
        """What is kept for the box ``cfg``."""
        s = self.stores()
        return {"mac": s["macs"].read(cfg.id), "volume": s["volume"].read(cfg.id),
                "mode": youtube_mode(cfg, s["modes"]), "failed": s["health"].for_box(cfg.id).failed_at(),
                "buttons": s["shortcuts"].custom(cfg.id)}

    def migrate(self):
        return boxids.migrate(self.path, self.state)


class ListFormTest(Folder):
    """042's config: a list keyed by host, and its per-box state."""

    def setUp(self):
        super().setUp()
        self.write({"youtubeMode": "youtube-first", "custom": {"kept": True}, "boxes": [
            {"name": "Living room", "host": "kodi.example.lan", "username": "kodi", "password": SECRET,
             "wakeOnLan": False, "eventPort": 9778, "x-note": "kept"},
            {"name": "Bedroom", "host": "bedroom.example.lan", "httpPort": 8081, "password": OTHER_SECRET},
        ]})
        self.put("mac.json", {"hosts": {"kodi.example.lan": MAC_A, "bedroom.example.lan": MAC_B,
                                        "gone.example.lan": "02:00:00:00:00:0c"}})
        self.put("volume.json", {"hosts": {"bedroom.example.lan": "tv"}})
        self.put("youtube-mode.json", {"hosts": {"kodi.example.lan": "sendtokodi-only"}})
        self.put("youtube-failed.json", {"hosts": {"bedroom.example.lan": 1500.0}})
        self.put("shortcuts.json", {"boxes": {"kodi.example.lan": [None, MOVIES.encode(), None, None, None],
                                              "bedroom.example.lan": [ADDON.encode(), None, None, None, None]}})
        self.put("box.json", {"host": "bedroom.example.lan"})
        self.before = [self.settings(c) for c in config.load_all(self.path)]

    def test_the_old_files_work_before_the_move(self):
        a, b = config.load_all(self.path)
        self.assertEqual((a.id, b.id, a.saved_id), ("kodi.example.lan", "bedroom.example.lan", False))
        self.assertEqual(self.before[0], {"mac": MAC_A, "volume": None, "mode": ("sendtokodi-only", "remote"),
                                          "failed": None, "buttons": [None, MOVIES, None, None, None]})
        self.assertEqual(self.before[1], {"mac": MAC_B, "volume": "tv", "mode": ("youtube-first", "config"),
                                          "failed": 1500.0, "buttons": [ADDON, None, None, None, None]})
        self.assertEqual(config.load(self.path, chosen=ChosenBox(self.state).read()).name, "Bedroom")

    def test_the_move(self):
        self.assertTrue(self.migrate())
        data = self.read()
        a_id, b_id = (b["id"] for b in data["boxes"])
        self.assertRegex(a_id, UUID_RE)
        self.assertRegex(b_id, UUID_RE)
        self.assertNotEqual(a_id, b_id)
        # Everything else in the config is as it was, the passwords too.
        self.assertEqual(data, {"youtubeMode": "youtube-first", "custom": {"kept": True}, "boxes": [
            {"id": a_id, "name": "Living room", "host": "kodi.example.lan", "username": "kodi", "password": SECRET,
             "wakeOnLan": False, "eventPort": 9778, "x-note": "kept"},
            {"id": b_id, "name": "Bedroom", "host": "bedroom.example.lan", "httpPort": 8081,
             "password": OTHER_SECRET}]})
        self.assertEqual(stat.S_IMODE(os.stat(self.path).st_mode), 0o600)
        self.assertEqual(os.listdir(os.path.dirname(self.path)), ["config.json"])  # no temp file left
        # The state is under the ids now, and reads the same.
        a, b = config.load_all(self.path)
        self.assertEqual((a.id, b.id, a.saved_id), (a_id, b_id, True))
        self.assertEqual([self.settings(a), self.settings(b)], self.before)
        self.assertEqual(self.get("mac.json"), {"boxes": {"gone.example.lan": "02:00:00:00:00:0c",
                                                          a_id: MAC_A, b_id: MAC_B}})  # not a box's: left alone
        self.assertEqual(self.get("volume.json"), {"boxes": {b_id: "tv"}})
        self.assertEqual(set(self.get("shortcuts.json")["boxes"]), {a_id, b_id})
        self.assertEqual(self.get("box.json"), {"id": b_id})  # the box in use stays in use
        for name in os.listdir(self.state):
            self.assertEqual(stat.S_IMODE(os.stat(os.path.join(self.state, name)).st_mode), 0o600, name)
        self.assertEqual(sorted(os.listdir(self.state)), [".boxes.lock", "box.json", "mac.json", "shortcuts.json",
                                                          "volume.json", "youtube-failed.json", "youtube-mode.json"])

    def test_the_move_happens_once(self):
        self.assertTrue(self.migrate())
        after = self.snapshot()
        self.assertFalse(self.migrate())
        self.assertEqual(self.snapshot(), after)

    def test_stopped_before_the_config_is_written(self):
        with mock.patch.object(config, "write_file", side_effect=OSError(28, "No space left on device")):
            with self.assertRaises(OSError):
                self.migrate()
        self.assertNotIn("id", json.dumps(self.read()["boxes"]))  # the config is as it was
        self.assertEqual([self.settings(c) for c in config.load_all(self.path)], self.before)  # by host
        self.assertTrue(self.migrate())  # the next start finishes it
        self.assertEqual([self.settings(c) for c in config.load_all(self.path)], self.before)

    def test_the_state_folder_cant_be_written(self):
        config_before = self.snapshot()
        os.chmod(self.state, 0o500)
        with self.assertRaises(OSError):
            self.migrate()
        os.chmod(self.state, 0o700)
        self.assertEqual(self.snapshot(), config_before)  # nothing changed
        self.assertEqual([self.settings(c) for c in config.load_all(self.path)], self.before)

    def test_a_config_it_cant_read_is_left_alone(self):
        for text, mode in (('{"boxes": [{"host": "kodi.example.lan"', 0o600),  # half edited
                           ('{"boxes": [{"host": "x/y"}]}', 0o600),
                           ('{"boxes": [{"id": "a1", "host": "a.example.lan"}, {"id": "a1", "host": "b.example.lan"}]}',
                            0o600)):
            self.write(text, mode)
            before = self.snapshot()
            self.assertFalse(self.migrate())
            self.assertEqual(self.snapshot(), before)

    def test_boxes_added_by_hand_get_an_id_too(self):
        self.migrate()
        data = self.read()
        data["boxes"].append({"name": "Attic", "host": "attic.example.lan"})
        self.write(data)
        self.assertTrue(self.migrate())
        ids = [b["id"] for b in self.read()["boxes"]]
        self.assertEqual(ids[:2], [b["id"] for b in data["boxes"][:2]])  # the others keep theirs
        self.assertRegex(ids[2], UUID_RE)

    def test_the_daemon_moves_them_when_it_reads_the_config(self):
        watcher = daemon.ConfigWatcher(self.path, ChosenBox(self.state),
                                       migrate=lambda: boxids.migrate(self.path, self.state))
        cfg = watcher()
        self.assertTrue(cfg.saved_id)
        self.assertEqual(cfg.name, "Bedroom")  # still the box in use
        self.assertEqual(self.settings(cfg), self.before[1])
        boxes_, current = watcher.boxes()
        self.assertEqual([c.id for c in boxes_], [b["id"] for b in self.read()["boxes"]])

    def test_the_daemon_carries_on_when_it_cant(self):
        def fails():
            raise OSError(13, "Permission denied")
        watcher = daemon.ConfigWatcher(self.path, ChosenBox(self.state), migrate=fails)
        with mock.patch("sys.stderr") as err:
            cfg = watcher()
        self.assertNotIn(SECRET, "".join(str(c) for c in err.mock_calls))
        self.assertEqual((cfg.id, cfg.saved_id), ("bedroom.example.lan", False))
        self.assertEqual(self.settings(cfg), self.before[1])


class OneBoxFormTest(Folder):
    """omakodi 0.2's config (one box at the top) and its one-box state files."""

    def test_the_move(self):
        self.write({"host": "kodi.example.lan", "username": "kodi", "password": SECRET, "youtubeMode": "smart"})
        self.put("mac.json", {"host": "kodi.example.lan", "mac": MAC_A})
        self.put("volume.json", {"host": "kodi.example.lan", "keys": "kodi"})
        self.put("youtube-mode.json", {"host": "kodi.example.lan", "mode": "youtube-only"})
        (old,) = config.load_all(self.path)
        before = self.settings(old)
        self.assertEqual((before["mac"], before["volume"], before["mode"]), (MAC_A, "kodi", ("youtube-only", "remote")))
        self.assertTrue(self.migrate())
        data = self.read()
        self.assertRegex(data["id"], UUID_RE)
        self.assertEqual(data, {"id": data["id"], "host": "kodi.example.lan", "username": "kodi",
                                "password": SECRET, "youtubeMode": "smart"})  # still the one-box form
        (box,) = config.load_all(self.path)
        self.assertEqual(box.id, data["id"])
        self.assertEqual(self.settings(box), before)
        self.assertEqual(self.get("mac.json"), {"boxes": {box.id: MAC_A}})
        self.assertFalse(self.migrate())

    def test_a_config_readable_by_others_isnt_moved(self):
        self.write({"host": "kodi.example.lan", "password": SECRET}, 0o644)
        before = self.snapshot()
        self.assertFalse(self.migrate())  # omakodi refuses it: the user fixes it first
        self.assertEqual({k: v for k, v in self.snapshot().items() if "config" in k},
                         {k: v for k, v in before.items() if "config" in k})


class BoxSettingsTest(Folder):
    """A box's settings go with its id: two boxes on one address, a change
    of address, and Delete."""

    def setUp(self):
        super().setUp()
        self.write({"boxes": [{"id": "a1", "name": "Living room", "host": "kodi.example.lan"},
                              {"id": "b2", "name": "Kodi on 8081", "host": "kodi.example.lan", "httpPort": 8081}]})
        self.book = boxes.BoxBook(self.path, ChosenBox(self.state))
        s = self.stores()
        s["macs"].save("a1", MAC_A)
        s["volume"].save("a1", "tv")
        s["modes"].save("a1", "sendtokodi-only")
        s["health"].for_box("a1").record_failure()
        s["shortcuts"].set("a1", 1, MOVIES)
        s["shortcuts"].set("b2", 0, ADDON)

    def by_id(self, box_id):
        return next(c for c in self.book.boxes() if c.id == box_id)

    def test_two_boxes_on_one_address_keep_their_own(self):
        a, b = self.by_id("a1"), self.by_id("b2")
        self.assertEqual(self.settings(a), {"mac": MAC_A, "volume": "tv", "mode": ("sendtokodi-only", "remote"),
                                            "failed": 2000.0, "buttons": [None, MOVIES, None, None, None]})
        self.assertEqual(self.settings(b), {"mac": None, "volume": None, "mode": ("smart", "config"),
                                            "failed": None, "buttons": [ADDON, None, None, None, None]})

    def test_a_new_address_keeps_the_settings(self):
        before = self.settings(self.by_id("a1"))
        saved = self.book.save("a1", {"name": "Lounge", "host": "192.0.2.40", "httpPort": 8080, "tcpPort": 9090})
        self.assertEqual((saved.id, saved.name, saved.host), ("a1", "Lounge", "192.0.2.40"))
        self.assertEqual(self.settings(self.by_id("a1")), before)
        self.assertEqual(self.book.boxes()[0].id, "a1")  # in its place

    def test_delete_clears_the_settings(self):
        self.book.delete("a1")
        self.assertEqual([c.id for c in self.book.boxes()], ["b2"])
        for name in ("mac.json", "volume.json", "youtube-mode.json", "youtube-failed.json", "shortcuts.json"):
            self.assertNotIn("a1", self.get(name)["boxes"], name)
        self.assertEqual(self.settings(self.by_id("b2"))["buttons"], [ADDON, None, None, None, None])  # not b2's
        # A box saved again at that address starts with none of it.
        new = self.book.save("", {"name": "Living room", "host": "kodi.example.lan"})
        self.assertEqual(self.settings(new), {"mac": None, "volume": None, "mode": ("smart", "config"),
                                              "failed": None, "buttons": [None] * 5})

    def test_a_known_mac_address_is_kept(self):
        """The daemon fills in a box's MAC address only while it has none."""
        calls = []

        class Kodi:
            def call(self, method, params=None):
                calls.append(method)
                return {"Network.MacAddress": MAC_B}

        d = daemon.Daemon(lambda: None, macs=MacStore(self.state), stops=StopNote(self.state),
                          art_cache=ArtCache(os.path.join(self.state, "art")), titles=TitleStore(self.state),
                          youtube_modes=mode_store(self.state),
                          health=YoutubeHealth(self.state), shortcuts=ShortcutStore(self.state),
                          volume_keys=HostValue("volume", "keys", daemon.VOLUME_KEYS, self.state))
        d._read_mac(Kodi(), self.by_id("a1"))
        self.assertEqual((calls, MacStore(self.state).read("a1")), ([], MAC_A))  # not asked, not changed
        d._read_mac(Kodi(), self.by_id("b2"))
        self.assertEqual((calls, MacStore(self.state).read("b2")), (["XBMC.GetInfoLabels"], MAC_B))


if __name__ == "__main__":
    unittest.main()
