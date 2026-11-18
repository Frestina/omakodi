import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fakekodi import FakeKodi  # noqa: E402
from omakodi import links, route  # noqa: E402
from omakodi.errors import USAGE, OmakodiError  # noqa: E402
from omakodi.rpc import Kodi  # noqa: E402
from omakodi.share import VIDEO_PLAYLIST as VIDEO_QUEUE, Sender  # noqa: E402
from omakodi.state import YoutubeHealth  # noqa: E402

VID = "dQw4w9WgXcQ"


class LinksTest(unittest.TestCase):
    def test_youtube_forms(self):
        for url in (
            f"https://www.youtube.com/watch?v={VID}",
            f"https://youtube.com/watch?feature=share&v={VID}&t=42",
            f"https://m.youtube.com/watch?v={VID}",
            f"https://music.youtube.com/watch?v={VID}&list=RDAMVM",
            f"https://www.youtube.com/shorts/{VID}",
            f"https://www.youtube.com/live/{VID}?si=abc",
            f"https://www.youtube.com/embed/{VID}",
            f"https://www.youtube-nocookie.com/embed/{VID}",
            f"https://www.youtube.com/v/{VID}",
            f"https://youtu.be/{VID}?si=xyz",
            f"HTTPS://WWW.YOUTUBE.COM/watch?v={VID}",
        ):
            with self.subTest(url=url):
                self.assertEqual(links.youtube_video_id(url), VID)

    def test_not_single_videos(self):
        for url in (
            "https://www.youtube.com/playlist?list=PLexample",
            "https://www.youtube.com/@examplechannel",
            "https://www.youtube.com/channel/UCexample",
            "https://www.youtube.com/watch?v=short",
            "https://www.youtube.com/",
            f"https://notyoutube.com/watch?v={VID}",
            f"https://youtube.com.example.net/watch?v={VID}",
            "https://vimeo.com/123456",
        ):
            with self.subTest(url=url):
                self.assertIsNone(links.youtube_video_id(url))

    def test_extract(self):
        self.assertEqual(links.extract_url(f"Look at this! https://youtu.be/{VID}."), f"https://youtu.be/{VID}")
        self.assertEqual(links.extract_url("(https://example.com/a?b=c)"), "https://example.com/a?b=c")
        self.assertEqual(links.extract_url("a https://x.example/1 b https://y.example/2"), "https://x.example/1")
        self.assertIsNone(links.extract_url("no link here"))
        self.assertIsNone(links.extract_url("ftp://example.com/file"))
        self.assertIsNone(links.extract_url(None))

    def test_paths(self):
        self.assertEqual(links.youtube_path(VID), f"plugin://plugin.video.youtube/play/?video_id={VID}")
        self.assertEqual(links.sendtokodi_path("https://example.com/v?a=1&b=2"),
                         "plugin://plugin.video.sendtokodi/?url=https%3A%2F%2Fexample.com%2Fv%3Fa%3D1%26b%3D2")


class RouteTest(unittest.TestCase):
    def test_table(self):
        yt = route.Route(True, True)
        yt_alone = route.Route(True, False)
        stk = route.SENDTOKODI
        cases = {
            # (mode, has_youtube, has_sendtokodi, failed_recently): expected
            ("smart", True, True, False): yt,
            ("smart", True, True, True): stk._replace(note=route.NOTE_FAILED_RECENTLY),
            ("smart", True, False, True): yt_alone,
            ("smart", False, True, False): stk,
            ("youtube-first", True, True, True): yt,
            ("youtube-first", True, False, False): yt_alone,
            ("youtube-first", False, True, False): stk,
            ("youtube-only", True, True, False): yt_alone,
            ("youtube-only", False, True, False): stk._replace(note=route.NOTE_NO_YOUTUBE),
            ("sendtokodi-only", True, True, False): stk,
            ("sendtokodi-only", True, False, False): route.Route(True, False, route.NOTE_NO_SENDTOKODI),
        }
        for args, expected in cases.items():
            with self.subTest(args=args):
                self.assertEqual(route.choose(*args), expected)
        for mode in ("smart", "youtube-first", "youtube-only", "sendtokodi-only"):
            self.assertIsNone(route.choose(mode, False, False, False))


class SenderTest(unittest.TestCase):
    def setUp(self):
        self.fake = FakeKodi().start()
        self.set_installed("plugin.video.youtube", "plugin.video.sendtokodi")
        self.fake.results["Player.GetActivePlayers"] = []
        self.fake.results["Playlist.GetProperties"] = {"size": 3}
        self.tmp = tempfile.TemporaryDirectory()
        self.health = YoutubeHealth(self.tmp.name)
        self.sender = Sender(Kodi(self.fake.config()), "smart", self.health)

    def tearDown(self):
        self.fake.stop()
        self.tmp.cleanup()

    def set_installed(self, *addons):
        self.installed = set(addons)

        def addon(params):
            return {"addon": {"addonid": params["addonid"], "enabled": params["addonid"] in self.installed}}

        self.fake.results["Addons.GetAddonDetails"] = addon

    def opened(self):
        return [p["item"].get("file") for m, p in self.fake.calls if m == "Player.Open"]

    def playing(self, playlistid, position, type="video"):
        self.fake.results["Player.GetActivePlayers"] = [{"playerid": 1, "type": type}]
        self.fake.results["Player.GetProperties"] = {"playlistid": playlistid, "position": position}

    def test_play_while_the_queue_plays_keeps_it(self):
        self.playing(VIDEO_QUEUE, 2)
        msg = self.sender.play("https://vimeo.com/123456")
        path = links.sendtokodi_path("https://vimeo.com/123456")
        calls = [(m, p) for m, p in self.fake.calls if m in ("Playlist.Insert", "Player.Open")]
        self.assertEqual(calls, [
            ("Playlist.Insert", {"playlistid": 1, "position": 3, "item": {"file": path}}),
            ("Player.Open", {"item": {"playlistid": 1, "position": 3}}),
        ])
        self.assertTrue(msg.startswith("Playing on Kodi"))

    def test_play_outside_the_queue_opens_the_item(self):
        for playlistid, position, kind in ((-1, -1, "video"), (0, 4, "audio"), (1, -1, "video"), (1, True, "video")):
            with self.subTest(playlistid=playlistid, position=position):
                self.fake.calls.clear()
                self.playing(playlistid, position, kind)
                self.sender.play("https://vimeo.com/123456")
                self.assertEqual(self.opened(), [links.sendtokodi_path("https://vimeo.com/123456")])
                self.assertNotIn("Playlist.Insert", self.fake.methods())

    def test_player_gone_meanwhile_opens_the_item(self):
        self.playing(1, 2)
        self.fake.errors["Player.GetProperties"] = "Failed to execute method."
        self.sender.play("https://vimeo.com/123456")
        self.assertEqual(self.opened(), [links.sendtokodi_path("https://vimeo.com/123456")])

    def test_youtube_link_plays_with_youtube_addon(self):
        msg = self.sender.play(f"https://youtu.be/{VID}")
        self.assertEqual(self.opened(), [links.youtube_path(VID)])
        self.assertTrue(msg.startswith("Playing on Kodi"))

    def test_other_link_plays_with_sendtokodi(self):
        self.sender.play("https://vimeo.com/123456")
        self.assertEqual(self.opened(), [links.sendtokodi_path("https://vimeo.com/123456")])

    def test_failed_recently_uses_sendtokodi_with_note(self):
        self.health.record_failure()
        msg = self.sender.play(f"https://youtu.be/{VID}")
        self.assertEqual(self.opened(), [links.sendtokodi_path(f"https://youtu.be/{VID}")])
        self.assertIn("failed recently", msg)

    def test_missing_sendtokodi(self):
        self.set_installed("plugin.video.youtube")
        with self.assertRaises(OmakodiError) as cm:
            self.sender.play("https://vimeo.com/123456")
        self.assertEqual(cm.exception.kind, "SendToKodi isn't installed")
        self.set_installed()
        with self.assertRaises(OmakodiError) as cm:
            self.sender.play(f"https://youtu.be/{VID}")
        self.assertEqual(cm.exception.kind, "SendToKodi isn't installed")
        self.assertEqual(self.opened(), [])

    def test_addon_unknown_to_kodi(self):
        self.fake.errors["Addons.GetAddonDetails"] = "Invalid params."
        with self.assertRaises(OmakodiError) as cm:
            self.sender.play("https://vimeo.com/123456")
        self.assertEqual(cm.exception.kind, "SendToKodi isn't installed")

    def test_no_link(self):
        with self.assertRaises(OmakodiError) as cm:
            self.sender.play("just words")
        self.assertEqual((cm.exception.kind, cm.exception.code), ("no link found", USAGE))

    def test_queue_when_idle_plays(self):
        msg = self.sender.queue("https://vimeo.com/123456")
        self.assertEqual(len(self.opened()), 1)
        self.assertNotIn("Playlist.Add", self.fake.methods())
        self.assertTrue(msg.startswith("Playing"))

    def test_queue_while_playing_adds(self):
        self.fake.results["Player.GetActivePlayers"] = [{"playerid": 1, "type": "video"}]
        msg = self.sender.queue(f"https://youtu.be/{VID}")
        self.assertEqual(self.opened(), [])
        add = [p for m, p in self.fake.calls if m == "Playlist.Add"]
        self.assertEqual(add, [{"playlistid": 1, "item": {"file": links.youtube_path(VID)}}])
        self.assertEqual(msg, "Queued on Kodi (3 in queue)")


class HealthTest(unittest.TestCase):
    def test_memory(self):
        now = [1000.0]
        with tempfile.TemporaryDirectory() as d:
            h = YoutubeHealth(d, now=lambda: now[0])
            self.assertFalse(h.failed_recently())
            h.record_failure()
            now[0] += 29 * 60
            self.assertTrue(h.failed_recently())
            now[0] += 2 * 60
            self.assertFalse(h.failed_recently())
            h.record_failure()
            h.clear()
            self.assertFalse(h.failed_recently())


if __name__ == "__main__":
    unittest.main()
