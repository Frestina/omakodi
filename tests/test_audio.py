"""The audio tracks in the state (ticket 027): bounded, plain, known indexes only."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import fakekodi  # noqa: E402,F401  (puts lib/ on the path)
from omakodi.audio import MAX_NAME, MAX_TRACKS, tracks  # noqa: E402


class TracksTest(unittest.TestCase):
    def test_tracks_and_current(self):
        props = {"audiostreams": [
            {"index": 0, "name": "", "language": "eng", "codec": "truehd_atmos", "channels": 8,
             "bitrate": 1, "isdefault": True},
            {"index": 3, "name": "Director's commentary", "language": "", "codec": "", "channels": 0}],
            "currentaudiostream": {"index": 3}}
        self.assertEqual(tracks(props), {"current": 3, "tracks": [
            {"index": 0, "name": "", "language": "eng", "codec": "TrueHD Atmos", "channels": "7.1"},
            {"index": 3, "name": "Director's commentary", "language": "", "codec": "", "channels": ""}]})

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
        self.assertEqual(t["codec"], "BBBBBBBBBBBB")
        self.assertEqual(len({t["index"] for t in got["tracks"]}), MAX_TRACKS)


if __name__ == "__main__":
    unittest.main()
