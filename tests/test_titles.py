"""Titles for queued links (ticket 032). No network: oEmbed is stubbed."""

import io
import json
import os
import sys
import tempfile
import unittest
import urllib.error

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fakekodi import FakeKodi  # noqa: E402
from omakodi import links, titles  # noqa: E402
from omakodi.rpc import Kodi  # noqa: E402
from omakodi.share import Sender  # noqa: E402
from omakodi.state import YoutubeHealth  # noqa: E402

VID = "aqz-KE-bpKQ"


class Answer(io.BytesIO):
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class OembedTest(unittest.TestCase):
    def lookup(self, body=None, error=None, status=200):
        asked = []

        def urlopen(req, timeout):
            asked.append((req.full_url, req.get_header("User-agent"), timeout))
            if error:
                raise error
            a = Answer(body if isinstance(body, bytes) else json.dumps(body).encode())
            a.status = status
            return a

        return titles.youtube_title(VID, urlopen=urlopen), asked

    def test_title(self):
        title, asked = self.lookup({"title": "Highland Cow\nGets a Bath", "author_name": "Example Farm"})
        self.assertEqual(title, "Highland Cow Gets a Bath")
        url, agent, timeout = asked[0]
        self.assertEqual(url, "https://www.youtube.com/oembed?format=json&url="
                              "https%3A%2F%2Fwww.youtube.com%2Fwatch%3Fv%3Daqz-KE-bpKQ")
        self.assertEqual((agent, timeout), ("omakodi", titles.OEMBED_TIMEOUT))

    def test_failures_give_no_title(self):
        for kwargs in ({"error": urllib.error.URLError("offline")}, {"error": TimeoutError()},
                       {"body": b"<html>"}, {"body": ["x"]}, {"body": {"title": 7}},
                       {"body": b"x" * (titles.MAX_OEMBED + 1)}, {"body": {"title": "x"}, "status": 404}):
            with self.subTest(**{k: str(v)[:30] for k, v in kwargs.items()}):
                self.assertEqual(self.lookup(**kwargs)[0], "")

    def test_long_title_is_cut(self):
        self.assertEqual(len(self.lookup({"title": "y" * 1000})[0]), titles.MAX_TITLE)


class LabelTest(unittest.TestCase):
    def test_link_label(self):
        self.assertEqual(titles.link_label("https://www.vimeo.com/123456/"), "vimeo.com/123456")
        self.assertEqual(titles.link_label("https://video.example.net/clip/7?token=x#t=3"), "video.example.net/clip/7")


class StoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = os.path.join(self.tmp.name, "omakodi")

    def tearDown(self):
        self.tmp.cleanup()

    def test_put_get_and_mode(self):
        s = titles.TitleStore(self.dir)
        self.assertEqual(s.get("plugin://a"), "")
        s.put("plugin://a", "Title A")
        self.assertEqual(titles.TitleStore(self.dir).get("plugin://a"), "Title A")
        self.assertEqual(os.stat(s.path).st_mode & 0o777, 0o600)
        self.assertEqual(os.stat(self.dir).st_mode & 0o777, 0o700)
        with open(s.path) as f:
            self.assertNotIn("plugin://a", f.read())  # keys are hashes
        s.put("plugin://a", "")  # no title: nothing stored or changed
        self.assertEqual(s.get("plugin://a"), "Title A")

    def test_bounded_newest_kept(self):
        s = titles.TitleStore(self.dir)
        for i in range(titles.MAX_TITLES + 5):
            s.put(f"plugin://{i}", f"T{i}")
        self.assertEqual(s.get("plugin://0"), "")
        self.assertEqual(s.get(f"plugin://{titles.MAX_TITLES + 4}"), f"T{titles.MAX_TITLES + 4}")
        with open(s.path) as f:
            self.assertEqual(len(json.load(f)), titles.MAX_TITLES)

    def test_junk_file_is_ignored(self):
        os.makedirs(self.dir)
        for junk in ("not json", "[1, 2]", '{"k": 5}', "x" * (titles.MAX_FILE + 1)):
            with open(os.path.join(self.dir, "titles.json"), "w") as f:
                f.write(junk)
            self.assertEqual(titles.TitleStore(self.dir).get("plugin://a"), "")


class QueueStoresTitleTest(unittest.TestCase):
    def setUp(self):
        self.fake = FakeKodi().start()
        self.fake.results["Addons.GetAddonDetails"] = lambda p: {"addon": {"enabled": True}}
        self.fake.results["Player.GetActivePlayers"] = [{"playerid": 1, "type": "video"}]
        self.fake.results["Playlist.GetProperties"] = {"size": 2}
        self.tmp = tempfile.TemporaryDirectory()
        self.store = titles.TitleStore(self.tmp.name)
        self.looked_up = []

        def lookup(video_id):
            self.looked_up.append(video_id)
            return "Highland Cow Gets a Bath"

        self.sender = Sender(Kodi(self.fake.config()), "smart", YoutubeHealth(self.tmp.name),
                             titles=self.store, youtube_title=lookup)

    def tearDown(self):
        self.fake.stop()
        self.tmp.cleanup()

    def test_youtube_title_stored_before_adding(self):
        stored_at_add = []
        self.fake.results["Playlist.Add"] = lambda p: stored_at_add.append(self.store.get(p["item"]["file"])) or "OK"
        self.sender.queue(f"https://youtu.be/{VID}")
        self.assertEqual(self.looked_up, [VID])
        self.assertEqual(stored_at_add, ["Highland Cow Gets a Bath"])

    def test_other_link_gets_its_host_and_path(self):
        self.sender.queue("https://vimeo.com/123456")
        self.assertEqual(self.looked_up, [])
        self.assertEqual(self.store.get(links.sendtokodi_path("https://vimeo.com/123456")), "vimeo.com/123456")

    def test_failed_lookup_falls_back_to_the_link(self):
        self.sender.youtube_title = lambda vid: ""
        self.sender.queue(f"https://www.youtube.com/watch?v={VID}")
        self.assertEqual(self.store.get(links.youtube_path(VID)), f"YouTube video {VID}")

    def test_unwritable_store_still_queues(self):
        blocker = os.path.join(self.tmp.name, "file")
        open(blocker, "w").close()
        self.sender.titles = titles.TitleStore(os.path.join(blocker, "sub"))
        self.assertTrue(self.sender.queue("https://vimeo.com/123456").startswith("Queued on Kodi"))


if __name__ == "__main__":
    unittest.main()
