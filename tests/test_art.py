"""Artwork: choosing, fetching and caching (ticket 024)."""

import os
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fakekodi import FakeKodi  # noqa: E402
from omakodi import art  # noqa: E402
from omakodi.errors import OmakodiError  # noqa: E402
from omakodi.rpc import Kodi  # noqa: E402

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
JPG = b"\xff\xd8\xff\xe0" + b"\x00" * 32
WEBP = b"RIFF\x10\x00\x00\x00WEBPVP8 " + b"\x00" * 16
POSTER = "image://http%3a%2f%2fmedia.example.lan%2fposter.jpg/"
THUMB = "image://http%3a%2f%2fi.example.net%2fthumb.png/"


class SourceTest(unittest.TestCase):
    def test_best_first(self):
        self.assertEqual(art.source({"art": {"thumb": THUMB, "poster": POSTER}, "thumbnail": THUMB}), POSTER)
        self.assertEqual(art.source({"art": {"fanart": POSTER}, "thumbnail": THUMB}), THUMB)
        self.assertEqual(art.source({"art": {"thumb": THUMB}}), THUMB)

    def test_only_image_urls(self):
        for item in ({}, {"art": "x"}, {"thumbnail": "http://media.example.lan/x.jpg"},
                     {"thumbnail": "image://" + "a" * art.MAX_URL}, {"art": {"poster": 7}}):
            self.assertEqual(art.source(item), "", item)

    def test_kind(self):
        self.assertEqual([art.kind(d) for d in (PNG, JPG, WEBP, b"<html>", b"", b"RIFF1234WAVE")],
                         ["png", "jpg", "webp", None, None, None])


class CacheTest(unittest.TestCase):
    def setUp(self):
        self.fake = FakeKodi().start()
        self.kodi = Kodi(self.fake.config())
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = os.path.join(self.tmp.name, "omakodi", "art")
        self.cache = art.ArtCache(self.dir, max_files=3, max_bytes=1000)

    def tearDown(self):
        self.fake.stop()
        self.tmp.cleanup()

    def test_fetch_with_login_and_reuse(self):
        self.fake.images[POSTER] = JPG
        path = self.cache.fetch(self.kodi, POSTER)
        self.assertTrue(path.endswith(".jpg") and path.startswith(self.dir))
        with open(path, "rb") as f:
            self.assertEqual(f.read(), JPG)
        self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)
        self.assertEqual(os.stat(self.dir).st_mode & 0o777, 0o700)
        self.assertEqual(os.stat(os.path.dirname(self.dir)).st_mode & 0o777, 0o700)
        self.assertNotIn("media.example.lan", path)
        self.assertEqual(self.cache.fetch(self.kodi, POSTER), path)
        self.assertEqual(self.cache.cached(POSTER), path)
        self.assertEqual(self.fake.image_requests, [POSTER])  # asked once

    def test_unusable_answers_give_no_art(self):
        self.fake.images[POSTER] = b"<html>not an image</html>"
        self.fake.images[THUMB] = PNG + b"\x00" * 1000  # over max_bytes
        self.assertEqual(self.cache.fetch(self.kodi, POSTER), "")
        self.assertEqual(self.cache.fetch(self.kodi, THUMB), "")
        self.assertEqual(self.cache.fetch(self.kodi, "image://missing/"), "")  # 404
        self.assertEqual(self.cache.fetch(self.kodi, ""), "")
        self.assertFalse(os.path.exists(self.dir) and os.listdir(self.dir))

    def test_wrong_login_raises(self):
        self.fake.images[POSTER] = JPG
        kodi = Kodi(self.fake.config(password="wrong"))
        with self.assertRaises(OmakodiError) as cm:
            self.cache.fetch(kodi, POSTER)
        self.assertEqual(cm.exception.kind, "wrong username or password")
        self.assertNotIn("media.example.lan", str(cm.exception))

    def test_prune_keeps_the_most_recent(self):
        urls = [f"image://http%3a%2f%2fmedia.example.lan%2f{i}.png/" for i in range(5)]
        paths = []
        for i, u in enumerate(urls):
            self.fake.images[u] = PNG
            paths.append(self.cache.fetch(self.kodi, u))
            os.utime(paths[-1], (time.time() + i, time.time() + i))
        self.cache.prune()
        self.assertEqual(sorted(os.listdir(self.dir)), sorted(os.path.basename(p) for p in paths[2:]))


if __name__ == "__main__":
    unittest.main()


class DemoPosterTest(unittest.TestCase):
    """The fake's made-up poster for the demo scene (ticket 045) is a PNG the art cache keeps."""

    def test_poster_png(self):
        import fakekodi
        import zlib
        png = fakekodi.poster_png(4, 6)
        self.assertEqual(art.kind(png), "png")
        self.assertEqual((int.from_bytes(png[16:20], "big"), int.from_bytes(png[20:24], "big")), (4, 6))
        idat = png.index(b"IDAT")
        size = int.from_bytes(png[idat - 4:idat], "big")
        self.assertEqual(len(zlib.decompress(png[idat + 4:idat + 4 + size])), 6 * (1 + 4 * 3))
