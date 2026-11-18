"""The details card's data (ticket 026): plain, bounded, empty fields left out."""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import fakekodi  # noqa: E402,F401  (puts lib/ on the path)
from omakodi import details as d  # noqa: E402
from omakodi.errors import AUTH, FAILED, UNREACHABLE, OmakodiError  # noqa: E402


class PlainTest(unittest.TestCase):
    def test_kodi_tags_go_and_cr_breaks_the_line(self):
        raw = "[B]Channel[/B][CR][COLOR=FFADD8E6]blue[/COLOR] [color red]red[/color] [I]x[/I] [LIGHT]l[/LIGHT]"
        self.assertEqual(d.plain(raw, 300, lines=True), "Channel\nblue red x l")
        self.assertEqual(d.plain(raw, 300), "Channel blue red x l")

    def test_other_brackets_stay(self):
        self.assertEqual(d.plain("Remastered [2019] [Director's Cut]", 300), "Remastered [2019] [Director's Cut]")

    def test_control_characters_and_blank_runs(self):
        raw = "one\x00two\x1b[31m\r\n\r\n\n\n  three\t four \u0085\ud800"
        self.assertEqual(d.plain(raw, 300, lines=True), "one two [31m\n\nthree four")
        self.assertEqual(d.plain("a\nb", 300), "a b")

    def test_bounded(self):
        s = d.plain("word " * 1000, 50)
        self.assertEqual(len(s), 50)
        self.assertTrue(s.endswith("…"))
        self.assertEqual(d.plain("x" * 50, 50), "x" * 50)

    def test_not_text(self):
        for v in (None, 7, ["a"], {"a": 1}, True):
            self.assertEqual(d.plain(v, 10), "")


class BadgesTest(unittest.TestCase):
    def test_resolution_steps(self):
        cases = [((720, 480), "SD"), ((1024, 576), "720p"), ((960, 544), "SD"), ((1280, 720), "720p"),
                 ((1920, 800), "1080p"), ((1920, 1080), "1080p"), ((3840, 2160), "4K"),
                 ((7680, 4320), "8K"), ((0, 1080), ""), ((99999, 99999), ""), (("1920", 1080), "")]
        for (w, h), want in cases:
            with self.subTest(w=w, h=h):
                self.assertEqual(d.resolution(w, h), want)

    def test_live_streams_first_then_the_library(self):
        library = {"video": [{"width": 1920, "height": 1080, "hdrtype": "hdr10"}],
                   "audio": [{"channels": 6, "codec": "ac3"}]}
        self.assertEqual(d.badges({"width": 3840, "height": 2160}, {"channels": 8, "codec": "eac3"}, library),
                         ["4K", "HDR10", "7.1", "E-AC3"])
        self.assertEqual(d.badges({}, {}, library), ["1080p", "HDR10", "5.1", "AC3"])
        self.assertEqual(d.badges(None, "x", None), [])
        self.assertEqual(d.badges({"width": 1920, "height": 1080}, {"channels": 2, "codec": "opus"}, {}),
                         ["1080p", "Stereo", "Opus"])

    def test_hdr_channels_codecs(self):
        self.assertEqual([d.hdr(x) for x in ("dolbyvision", "HLG", "hdr10+", "something", "", None)],
                         ["Dolby Vision", "HLG", "HDR10+", "HDR", "", ""])
        self.assertEqual([d.channels(x) for x in (1, 2, 3, 6, 8, 0, -1, 65, "2", True)],
                         ["Mono", "Stereo", "3 ch", "5.1", "7.1", "", "", "", "", ""])
        self.assertEqual([d.codec(x) for x in ("dtshd_ma", "dtshd_ma_x", "truehd_atmos", "pcm_s24le",
                                               "weird codec<b>!", "x" * 40, "", None)],
                         ["DTS-HD MA", "DTS:X", "TrueHD Atmos", "PCM", "WEIRDCODECB", "X" * 12, "", ""])


class DetailsTest(unittest.TestCase):
    def test_library_movie(self):
        item = {"plot": "", "plotoutline": "A keeper finds a map.", "genre": ["Drama", "Drama", "", 3, "Mystery"],
                "year": 0, "premiered": "2019-03-01", "studio": ["Northlight", "Harbour Films", "Third"],
                "rating": 7.0, "cast": [{"name": f"Actor {i}", "role": "x"} for i in range(30)] + ["junk"],
                "file": "http://media.example.lan/stream?api_key=secret"}
        got = d.details(item, {})
        self.assertEqual(got, {"plot": "A keeper finds a map.", "genres": ["Drama", "Mystery"], "year": 2019,
                               "studio": "Northlight, Harbour Films", "rating": "7.0",
                               "cast": [f"Actor {i}" for i in range(10)]})
        self.assertNotIn("api_key", json.dumps(got))

    def test_empty_fields_left_out(self):
        self.assertIsNone(d.details({}, {}))
        self.assertIsNone(d.details(None, None))
        self.assertIsNone(d.details({"plot": "  ", "genre": [], "year": 0, "rating": 0, "cast": []}, {}))
        self.assertEqual(d.details({"plot": "[B][/B]Only a plot"}, None), {"plot": "Only a plot"})

    def test_bounds(self):
        long = "é" * 500
        item = {"plot": long * 20, "genre": [long] * 20, "studio": [long] * 5, "year": 99999,
                "firstaired": "1999-12-31", "rating": 11, "cast": [{"name": long}] * 50}
        got = d.details(item, {"currentvideostream": {"width": 1920, "height": 1080},
                               "currentaudiostream": {"channels": 2, "codec": long}})
        self.assertEqual(len(got["plot"]), d.MAX_PLOT)
        self.assertEqual([len(g) for g in got["genres"]], [d.MAX_GENRE])  # the same name once
        self.assertLessEqual(len(got["studio"]), d.MAX_STUDIO)
        self.assertEqual(got["year"], 1999)
        self.assertNotIn("rating", got)
        self.assertEqual([len(c) for c in got["cast"]], [d.MAX_NAME])
        self.assertLessEqual(len(got["badges"]), d.MAX_BADGES)
        self.assertTrue(all(len(b) <= d.MAX_BADGE for b in got["badges"]))
        # Far below the shell's 64 KiB line limit, even next to a full queue.
        self.assertLess(len(json.dumps(got, ensure_ascii=False).encode()), 12 * 1024)

    def test_year(self):
        self.assertEqual(d.year({"year": 2001}), 2001)
        self.assertEqual(d.year({"year": 0, "premiered": "", "firstaired": "2010-05-04"}), 2010)
        self.assertEqual(d.year({"year": True, "premiered": "1066-01-01"}), 0)
        self.assertEqual(d.year({"premiered": "soon"}), 0)


class FakeKodi:
    def __init__(self, answers):
        self.answers = answers
        self.calls = []

    def call(self, method, params=None):
        self.calls.append((method, params))
        got = self.answers.get(method)
        if isinstance(got, Exception):
            raise got
        return got


class ReadTest(unittest.TestCase):
    def test_asks_for_details_never_the_file(self):
        kodi = FakeKodi({"Player.GetItem": {"item": {"plot": "p"}},
                         "Player.GetProperties": {"currentvideostream": {"width": 1280, "height": 720}}})
        self.assertEqual(d.read_details(kodi, 1), ({"plot": "p", "badges": ["720p"]}, True))
        for method, params in kodi.calls:
            self.assertEqual(params["playerid"], 1)
            self.assertNotIn("file", params["properties"])

    def test_unusable_answers_give_no_details(self):
        kodi = FakeKodi({"Player.GetItem": OmakodiError("kodi error", "Invalid params", FAILED),
                         "Player.GetProperties": OmakodiError("bad response", "", FAILED)})
        self.assertEqual(d.read_details(kodi, 1), (None, False))

    def test_lost_connection_and_wrong_password_fail(self):
        for code in (UNREACHABLE, AUTH):
            kodi = FakeKodi({"Player.GetItem": OmakodiError("x", "", code)})
            with self.assertRaises(OmakodiError):
                d.read_details(kodi, 1)


if __name__ == "__main__":
    unittest.main()
