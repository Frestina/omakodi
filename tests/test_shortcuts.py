"""The shortcut buttons (SPEC "Shortcut buttons"): paths, the store, the picker."""

import json
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fakekodi import ROOT, FakeKodi  # noqa: E402
from omakodi import shortcuts as sc  # noqa: E402
from omakodi.errors import OmakodiError  # noqa: E402
from omakodi.rpc import Kodi  # noqa: E402


class PathTest(unittest.TestCase):
    def test_normalize(self):
        for typed, path in (
            ("plugin.video.youtube", "plugin://plugin.video.youtube/"),
            ("  plugin://plugin.video.youtube ", "plugin://plugin.video.youtube/"),
            ("PLUGIN://plugin.video.youtube", "PLUGIN://plugin.video.youtube/"),
            ("plugin://plugin.video.youtube/feeds/", "plugin://plugin.video.youtube/feeds/"),
            ("plugin://plugin.video.youtube?x=1", "plugin://plugin.video.youtube?x=1"),
            ("videodb://movies/titles/", "videodb://movies/titles/"),
            ("smb://nas.example.lan/My Films/", "smb://nas.example.lan/My Films/"),
            ("script.example.tool", "script.example.tool"),
            ("Plugin.Audio.Example", "plugin://Plugin.Audio.Example/"),
        ):
            with self.subTest(typed=typed):
                self.assertEqual(sc.normalize(typed), path)
        for bad in ("", "   ", "youtube", "plugin.", ".video", "a b.c", "x\n://y", None, 7,
                    "smb://" + "a" * sc.MAX_PATH):
            with self.subTest(bad=bad):
                self.assertIsNone(sc.normalize(bad))

    def test_addon_and_window(self):
        self.assertEqual(sc.addon_id("plugin://plugin.video.youtube/feeds/?x=1"), "plugin.video.youtube")
        self.assertEqual(sc.addon_id("script.example.tool"), "script.example.tool")
        self.assertIsNone(sc.addon_id("videodb://movies/titles/"))
        self.assertIsNone(sc.addon_id(None))
        for path, window in (("plugin://plugin.audio.radio/", "music"), ("musicdb://albums/", "music"),
                             ("library://music/genres.xml/", "music"), ("plugin://plugin.image.x/", "pictures"),
                             ("plugin://plugin.program.x/", "programs"), ("plugin://plugin.video.x/", "videos"),
                             ("smb://nas.example.lan/", "videos")):
            self.assertEqual(sc.window_for(path), window)

    def test_open_call(self):
        self.assertEqual(sc.open_call(sc.DEFAULTS[0]), ("GUI.ActivateWindow", {"window": "home"}))
        self.assertEqual(sc.open_call(sc.DEFAULTS[1]), ("GUI.ActivateWindow", {
            "window": "videos", "parameters": ["videodb://movies/titles/", "return"]}))
        typed = sc.Shortcut(path="plugin://plugin.audio.radio/", typed=True)
        self.assertEqual(sc.open_call(typed), ("GUI.ActivateWindow", {
            "window": "music", "parameters": ["plugin://plugin.audio.radio/", "return"]}))
        self.assertEqual(sc.open_call(sc.Shortcut(path="script.example.tool")),
                         ("Addons.ExecuteAddon", {"addonid": "script.example.tool"}))
        with self.assertRaises(OmakodiError) as e:
            sc.open_call(sc.DEFAULTS[4])
        self.assertEqual(e.exception.kind, "that button sends a link")

    def test_auto_icons(self):
        icon = sc.auto_icon
        self.assertEqual([icon(s) for s in sc.DEFAULTS], ["home", "movie", "tv", "headphones", "link"])
        self.assertEqual(icon(sc.Shortcut(path="special://profile/playlists/video/x.xsp")), "playlist")
        self.assertEqual(icon(sc.Shortcut(path="plugin://plugin.video.x/")), "addon")
        self.assertEqual(icon(sc.Shortcut(window="videos", path="videodb://musicvideos/titles/")), "music_video")
        self.assertEqual(icon(sc.Shortcut(window="weather")), "weather")
        self.assertEqual(icon(sc.Shortcut(window="somethingnew")), "folder")
        self.assertEqual(icon(sc.Shortcut(window="videos", path="smb://nas.example.lan/")), "folder")
        self.assertTrue(all(i in sc.ICONS for i in sc.WINDOW_ICONS.values()))
        self.assertEqual(len(set(sc.ICONS)), len(sc.ICONS))
        self.assertTrue(60 <= len(sc.ICONS) <= 80, len(sc.ICONS))

    def test_art_url(self):
        self.assertEqual(sc.art_url("image://x.png/"), "image://x.png/")
        self.assertEqual(sc.art_url("special://home/addons/plugin.video.x/icon.png"),
                         "image://special%3A%2F%2Fhome%2Faddons%2Fplugin.video.x%2Ficon.png/")
        for bad in ("", None, 7, "image://a\nb/", "x" * (sc.MAX_ART + 1)):
            self.assertEqual(sc.art_url(bad), "")


class StoreTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.store = sc.ShortcutStore(os.path.join(self.dir.name, "state"))

    def tearDown(self):
        self.dir.cleanup()

    def test_kept_per_box_with_mode_600(self):
        self.assertEqual(self.store.buttons("kodi.example.lan"), [(s, False) for s in sc.DEFAULTS])
        picked = sc.Shortcut("Example › Trending", "videos", "plugin://plugin.video.example/trending/",
                             art="image://thumb.png/")
        self.store.set("kodi.example.lan", 2, picked)
        self.assertEqual(os.stat(self.store.path).st_mode & 0o777, 0o600)
        self.assertEqual(os.stat(os.path.dirname(self.store.path)).st_mode & 0o777, 0o700)
        again = sc.ShortcutStore(os.path.dirname(self.store.path))
        self.assertEqual(again.custom("kodi.example.lan"), [None, None, picked, None, None])
        self.assertEqual(again.custom("other.example.lan"), [None] * 5)
        # the default itself is kept as "default"; a changed icon is kept
        self.store.set("kodi.example.lan", 0, sc.DEFAULTS[0])
        self.store.set("kodi.example.lan", 1, sc.DEFAULTS[1].replace(icon="film"))
        self.assertEqual(again.custom("kodi.example.lan")[:2], [None, sc.DEFAULTS[1].replace(icon="film")])
        self.store.set("kodi.example.lan", 1, None)
        self.store.set("kodi.example.lan", 2, None)
        with open(self.store.path) as f:
            self.assertEqual(json.load(f), {"boxes": {}})
        with self.assertRaises(ValueError):
            self.store.set("kodi.example.lan", 5, None)

    def test_at_most_32_boxes(self):
        for i in range(40):
            self.store.set(f"box{i}.example.lan", 0, sc.DEFAULTS[4])
        with open(self.store.path) as f:
            boxes = list(json.load(f)["boxes"])
        self.assertEqual(boxes, [f"box{i}.example.lan" for i in range(8, 40)])

    def test_junk_is_ignored(self):
        os.makedirs(os.path.dirname(self.store.path))
        good = sc.DEFAULTS[1].replace(icon="film").encode()
        cases = [
            b"not json", b"[]", json.dumps({"boxes": []}).encode(),
            json.dumps({"boxes": {"kodi.example.lan": [None] * 4}}).encode(),
        ]
        for raw in cases:
            with open(self.store.path, "wb") as f:
                f.write(raw)
            self.assertEqual(self.store.custom("kodi.example.lan"), [None] * 5)
        slots = [{"action": "rocket"}, {"window": "Bad Window"}, {"path": "a\x00b"}, {"label": "only a label"},
                 {**good, "icon": "rocket", "art": 5, "label": "[B]Films[/B]"}]
        with open(self.store.path, "w") as f:
            json.dump({"boxes": {"kodi.example.lan": slots}}, f)
        got = self.store.custom("kodi.example.lan")
        self.assertEqual(got[:4], [None] * 4)
        self.assertEqual(got[4], sc.Shortcut("Films", "videos", "videodb://movies/titles/"))


class PickerTest(unittest.TestCase):
    def setUp(self):
        self.fake = FakeKodi().start()
        self.kodi = Kodi(self.fake.config())

    def tearDown(self):
        self.fake.stop()

    def test_pages_list_what_kodi_has(self):
        self.fake.results["Favourites.GetFavourites"] = {"favourites": [
            {"title": "Late films", "type": "window", "window": "videos",
             "windowparameter": "videodb://movies/genres/", "thumbnail": "image://fav.png/"},
            {"title": "A song", "type": "media", "path": "/music/a.mp3"},
            {"title": "Weather", "type": "window", "window": "weather"}]}
        favs = sc.load(self.kodi, sc.Page("favourites", "Favourites"))
        self.assertEqual([(i.label, i.choose) for i in favs], [
            ("Late films", sc.Shortcut("Late films", "videos", "videodb://movies/genres/", art="image://fav.png/")),
            ("Weather", sc.Shortcut("Weather", "weather"))])
        self.fake.results["Files.GetSources"] = {"sources": [{"label": "Music", "file": "nfs://nas.example.lan/music/"}]}
        page = sc.load(self.kodi, sc.Page("sources", "Music sources", media="music", window="music"))[0].browse
        self.assertEqual((page.arg, page.media, page.window, page.folder), ("nfs://nas.example.lan/music/", "music",
                                                                            "music", True))
        self.assertEqual(page.as_shortcut(), sc.Shortcut("Music", "music", "nfs://nas.example.lan/music/"))
        self.fake.results["Files.GetDirectory"] = {"files": [{"file": "x", "filetype": "directory", "label": ""}]}
        self.assertEqual(sc.load(self.kodi, page), [])
        method, params = self.fake.calls[-1]
        self.assertEqual((method, params["media"]), ("Files.GetDirectory", "music"))
        common = [i.choose.window for i in sc.load(None, sc.Page("static", "Common", "common"))]
        self.assertEqual(common[:5], ["home", "videos", "videos", "videos", "music"])

    def test_the_stack_and_old_lists(self):
        p = sc.Picker()
        p.start()
        page, seq = p.needs_load()
        self.assertEqual(page.kind, "root")
        self.assertTrue(p.loaded(seq, sc.load(None, page)))
        view = p.view()
        self.assertEqual((view["status"], view["depth"], len(view["items"])), ("ready", 1, 10))
        p.open(view["seq"], 1)  # Video library
        page, seq = p.needs_load()
        self.assertFalse(p.loaded(seq - 1, []))  # an answer for an older page
        p.loaded(seq, sc.load(None, page))
        view = p.view()
        self.assertEqual(p.chosen(view["seq"], 0), sc.Shortcut("Movies", "videos", "videodb://movies/titles/"))
        with self.assertRaises(OmakodiError):
            p.chosen(view["seq"], -1)  # not a folder
        with self.assertRaises(OmakodiError):
            p.open(view["seq"], 0)  # a pick, not a page
        with self.assertRaises(OmakodiError):
            p.open(view["seq"] - 1, 9)
        p.open(view["seq"], 9)  # Video playlists, a folder
        _, seq = p.needs_load()
        p.loaded(seq, error="not reachable: …")
        view = p.view()
        self.assertEqual((view["status"], view["folder"], view["depth"]), ("failed", True, 3))
        self.assertEqual(p.chosen(view["seq"], -1).path, "special://videoplaylists/")
        p.back(view["seq"])
        self.assertEqual(p.view()["title"], "Video library")
        self.assertEqual(p.needs_load()[0], None)  # still there
        p.back(p.view()["seq"])
        p.back(p.view()["seq"])  # the first page stays
        self.assertEqual(p.view()["depth"], 1)


class CliTest(unittest.TestCase):
    def test_omakodi_shortcut(self):
        fake = FakeKodi().start()
        try:
            with tempfile.TemporaryDirectory() as d:
                cfg = os.path.join(d, "config.json")
                fd = os.open(cfg, os.O_WRONLY | os.O_CREAT, 0o600)
                with os.fdopen(fd, "w") as f:
                    json.dump(fake.config_json(), f)
                sc.ShortcutStore(os.path.join(d, "omakodi")).set(
                    "127.0.0.1", 3, sc.Shortcut(path="plugin://plugin.audio.radio/", typed=True))
                env = dict(os.environ, OMAKODI_CONFIG=cfg, XDG_STATE_HOME=d)
                run = lambda n: subprocess.run([os.path.join(ROOT, "bin", "omakodi"), "shortcut", n], env=env,
                                               capture_output=True, text=True, timeout=10)
                self.assertEqual(run("2").returncode, 0)
                self.assertEqual(run("4").returncode, 0)
                r = run("5")
                self.assertEqual(r.returncode, 2)
                self.assertIn("that button sends a link", r.stderr)
                self.assertEqual(run("6").returncode, 2)
                self.assertEqual([p for m, p in fake.calls], [
                    {"window": "videos", "parameters": ["videodb://movies/titles/", "return"]},
                    {"window": "music", "parameters": ["plugin://plugin.audio.radio/", "return"]}])
        finally:
            fake.stop()


if __name__ == "__main__":
    unittest.main()
