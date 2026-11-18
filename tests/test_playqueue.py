"""The queue window (ticket 025)."""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import fakekodi  # noqa: E402,F401  (puts lib/ on the path)
from omakodi.playqueue import BEFORE, WINDOW, window  # noqa: E402


class WindowTest(unittest.TestCase):
    def test_short_queue_whole(self):
        self.assertEqual(window(0, 0), (0, 0))
        self.assertEqual(window(3, WINDOW), (0, WINDOW))

    def test_long_queue_around_the_playing_one(self):
        total = 500
        self.assertEqual(window(5, total), (0, WINDOW))
        self.assertEqual(window(250, total), (250 - BEFORE, 250 - BEFORE + WINDOW))
        self.assertEqual(window(499, total), (total - WINDOW, total))
        for pos in range(total):
            start, end = window(pos, total)
            self.assertTrue(start <= pos < end and end - start == WINDOW, pos)


class SizeTest(unittest.TestCase):
    def test_a_full_window_of_long_titles_fits_one_line(self):
        from fakekodi import FakeKodi
        from omakodi.playqueue import read_queue
        from omakodi.rpc import Kodi
        fake = FakeKodi().start()
        try:
            long = "\u00e9" * 300  # as long as Kodi's titles get here
            entries = [{"title": long, "showtitle": long, "season": 1, "episode": 2}] * 300
            fake.results["Playlist.GetItems"] = lambda p: {
                "items": entries[p["limits"]["start"]:p["limits"]["end"]]}
            q = read_queue(Kodi(fake.config()), 0, 300)
        finally:
            fake.stop()
        self.assertEqual(len(q["items"]), WINDOW)
        # As the daemon writes it; Protocol.js counts the characters.
        line = json.dumps({"type": "state", "queue": q, "playing": {"title": long[:300]}},
                          ensure_ascii=False, separators=(",", ":"))
        self.assertLess(len(line), 40 * 1024)

    def test_an_unusable_answer_shows_no_entries(self):
        from fakekodi import FakeKodi
        from omakodi.errors import OmakodiError
        from omakodi.playqueue import read_queue
        from omakodi.rpc import Kodi
        fake = FakeKodi().start()
        try:
            fake.results["Playlist.GetItems"] = {"items": [{"title": "x" * 1000}] * 2000}  # over 1 MB
            self.assertEqual(read_queue(Kodi(fake.config()), 0, 3)["items"], [])
            fake.errors["Playlist.GetItems"] = "Invalid params."
            self.assertEqual(read_queue(Kodi(fake.config()), 0, 3),
                             {"position": 0, "start": 0, "total": 3, "items": []})
            with self.assertRaises(OmakodiError):
                read_queue(Kodi(fake.config(password="wrong")), 0, 3)
        finally:
            fake.stop()


if __name__ == "__main__":
    unittest.main()
