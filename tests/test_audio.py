"""The audio tracks in the state (tickets 027, 051): bounded, plain, known
indexes only; codec and channels worded as the phone remote does."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import fakekodi  # noqa: E402,F401  (puts lib/ on the path)
from omakodi.audio import MAX_CODEC, MAX_NAME, MAX_TRACKS, tracks  # noqa: E402
from omakodi.languages import MAX_NAME as MAX_LANGUAGE_NAME, NAMES, name  # noqa: E402


class TracksTest(unittest.TestCase):
    def test_tracks_and_current(self):
        props = {"audiostreams": [
            {"index": 0, "name": "", "language": "eng", "codec": "truehd_atmos", "channels": 8,
             "bitrate": 1, "isdefault": True},
            {"index": 3, "name": "Director's commentary", "language": "", "codec": "", "channels": 0}],
            "currentaudiostream": {"index": 3}}
        self.assertEqual(tracks(props), {"current": 3, "tracks": [
            {"index": 0, "name": "", "language": "English", "codec": "TRUEHD_ATMOS", "channels": "7.1"},
            {"index": 3, "name": "Director's commentary", "language": "", "codec": "", "channels": ""}]})

    def test_codec_and_channels_as_kodi_says_them(self):
        cases = [("ac3", 6, "AC3", "5.1"), ("eac3", 2, "EAC3", "stereo"), ("truehd", 8, "TRUEHD", "7.1"),
                 ("dca", 1, "DCA", "mono"), ("dts", 3, "DTS", "3 ch"), (" pcm_s16le ", 0, "PCM_S16LE", ""),
                 ("dtshd-ma", 65, "DTSHD-MA", ""), ("", True, "", ""), (None, "6", "", ""), (7, -2, "", "")]
        for kodi_codec, kodi_channels, want_codec, want_channels in cases:
            t = tracks({"audiostreams": [{"index": 0, "codec": kodi_codec, "channels": kodi_channels}]})["tracks"][0]
            self.assertEqual((t["codec"], t["channels"]), (want_codec, want_channels), kodi_codec)

    def test_tags_removed_from_the_name(self):
        streams = [{"index": 0, "name": "[B]VFF[/B] - [COLOR yellow]DD+ 5.1[/COLOR]"},
                   {"index": 1, "name": "[I]Commentary[/I][CR]with the director"},
                   {"index": 2, "name": "[LIGHT][/LIGHT]"}]
        names = [t["name"] for t in tracks({"audiostreams": streams})["tracks"]]
        self.assertEqual(names, ["VFF - DD+ 5.1", "Commentary with the director", ""])

    def test_current_not_listed(self):
        for current in ({"index": 9}, {}, None, "x", {"index": True}):
            got = tracks({"audiostreams": [{"index": 0}], "currentaudiostream": current})
            self.assertEqual(got["current"], -1, current)

    def test_nothing_to_list(self):
        for props in ({}, None, {"audiostreams": []}, {"audiostreams": "x"},
                      {"audiostreams": [{"index": -1}, {"index": 1000}, {"index": "1"}, {"index": True}, 7]}):
            self.assertIsNone(tracks(props), props)

    def test_bounds_and_plain_text(self):
        streams = [{"index": i, "name": "[COLOR red]x[/COLOR]\n" + "n" * 500, "language": "en<script>" + "g" * 40,
                    "codec": "<b>" * 20, "channels": 6} for i in range(100)] + [{"index": 0, "name": "dup"}]
        got = tracks({"audiostreams": streams, "currentaudiostream": {"index": 50}})
        self.assertEqual(len(got["tracks"]), MAX_TRACKS)
        self.assertEqual(got["current"], -1)  # past the 32 listed
        t = got["tracks"][0]
        self.assertEqual(len(t["name"]), MAX_NAME)
        self.assertTrue(t["name"].startswith("x n"))
        self.assertEqual(t["language"], "enscript" + "g" * 12)
        self.assertEqual(t["codec"], "B" * MAX_CODEC)
        self.assertEqual(len({t["index"] for t in got["tracks"]}), MAX_TRACKS)


class LanguageTest(unittest.TestCase):
    def test_codes(self):
        cases = {"eng": "English", "en": "English", "ENG": "English", " fre ": "French", "fra": "French",
                 "fr": "French", "ger": "German", "deu": "German", "nor": "Norwegian", "nob": "Norwegian Bokmål",
                 "nno": "Norwegian Nynorsk", "swe": "Swedish", "dan": "Danish", "jpn": "Japanese",
                 "chi": "Chinese", "zho": "Chinese", "fil": "Filipino"}
        for code, want in cases.items():
            self.assertEqual(name(code), want, code)

    def test_regions_and_scripts(self):
        self.assertEqual([name(c) for c in ("en-US", "pt_BR", "es-419", "zh-Hant", "sr-latn")],
                         ["English (US)", "Portuguese (BR)", "Spanish (419)", "Chinese (Hant)", "Serbian (Latn)"])

    def test_none_and_unknown(self):
        for code in ("", "und", "UND", "unk", "mul", "zxx", None, 7, ["en"]):
            self.assertEqual(name(code), "", code)
        self.assertEqual(name("xyz"), "xyz")
        self.assertEqual(name("en-<b>"), "en-b")  # not a region: kept as an unknown code, cleaned
        self.assertEqual(name("q" * 99), "q" * 20)

    def test_every_name_fits(self):
        self.assertTrue(all(len(n) <= MAX_LANGUAGE_NAME for n in NAMES.values()))
        self.assertTrue(all(len(name(c + "-ABCDEFGH")) <= MAX_LANGUAGE_NAME for c in NAMES))
        for code in NAMES:  # two- and three-letter codes only
            self.assertIn(len(code), (2, 3), code)


if __name__ == "__main__":
    unittest.main()
