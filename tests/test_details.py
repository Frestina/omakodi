"""The Details dialog's data (tickets 026, 046): plain, bounded, empty fields left out."""

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

    def test_colour_written_without_a_space(self):
        # as some add-ons write their names (ticket 041)
        self.assertEqual(d.plain("[COLORghostwhite]Example Channel[/COLOR]", 300), "Example Channel")

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
        library = {"video": [{"width": 1920, "height": 1080, "codec": "h264", "hdrtype": "hdr10"}],
                   "audio": [{"channels": 6, "codec": "ac3"}]}
        self.assertEqual(d.badges({"width": 3840, "height": 2160, "codec": "hevc"}, {"channels": 8, "codec": "eac3"},
                                  library), ["4K", "HEVC", "HDR10", "DD+", "7.1"])
        self.assertEqual(d.badges({}, {}, library), ["1080p", "H.264", "HDR10", "DD", "5.1"])
        self.assertEqual(d.badges(None, "x", None), [])
        # A YouTube stream as Kodi 21 reports it: no HDR type while it plays.
        self.assertEqual(d.badges({"width": 1920, "height": 1080, "codec": "h264"}, {"channels": 2, "codec": "aac"}, {}),
                         ["1080p", "H.264", "AAC", "2.0"])
        self.assertEqual(d.badges({"width": 3840, "height": 2160, "codec": "vp9", "hdrtype": "hlg"},
                                  {"channels": 2, "codec": "opus"}, {}), ["4K", "VP9", "HLG", "Opus", "2.0"])

    def test_hdr_channels_codecs(self):
        self.assertEqual([d.hdr(x) for x in ("dolbyvision", "HLG", "hdr10+", "something", "", None)],
                         ["Dolby Vision", "HLG", "HDR10+", "HDR", "", ""])
        self.assertEqual([d.channels(x) for x in (1, 2, 3, 6, 8, 0, -1, 65, "2", True)],
                         ["Mono", "Stereo", "3 ch", "5.1", "7.1", "", "", "", "", ""])
        self.assertEqual([d.channels_badge(x) for x in (1, 2, 6, 8, 3, 0)], ["Mono", "2.0", "5.1", "7.1", "3 ch", ""])
        self.assertEqual([d.codec(x) for x in ("dtshd_ma", "dtshd_ma_x", "truehd_atmos", "pcm_s24le",
                                               "weird codec<b>!", "x" * 40, "", None)],
                         ["DTS-HD MA", "DTS:X", "TrueHD Atmos", "PCM", "WEIRDCODECB", "X" * 12, "", ""])
        # The audio tracks keep their words (ticket 034); the badges say DD and DD+.
        self.assertEqual([d.codec(x) for x in ("ac3", "eac3")], ["AC3", "E-AC3"])
        self.assertEqual([d.audio_badge(x) for x in ("ac3", "EAC3", "eac3_ddp_atmos", "truehd", "dca", None)],
                         ["DD", "DD+", "DD+ Atmos", "TrueHD", "DTS", ""])
        self.assertEqual([d.video_codec(x) for x in ("hevc", "H264", "avc1", "av1", "mpeg2video", "vc1",
                                                     "new<codec>", "", None)],
                         ["HEVC", "H.264", "H.264", "AV1", "MPEG-2", "VC-1", "NEWCODEC", "", ""])


# A library film as Kodi gives it (made up), with a photo URL that carries a
# media server's key: it must never reach the state.
FILM = {
    "type": "movie", "id": 7, "label": "Harbour Lights", "title": "Harbour Lights", "showtitle": "",
    "season": -1, "episode": -1, "artist": [], "plot": "", "plotoutline": "A keeper finds a map.",
    "tagline": "Follow the light", "genre": ["Drama", "Drama", "", 3, "Mystery"], "year": 2019,
    "premiered": "2019-03-01", "firstaired": "", "studio": ["Northlight", "Harbour Films"],
    "rating": 7.84, "votes": "12345", "mpaa": "Rated PG-13", "runtime": 6720,
    "director": ["Mara Example"], "writer": ["Ivo Sample", "Lena Draft"], "country": ["Norway", "Iceland"],
    "cast": [{"name": "Tom Byway", "role": "Ferryman", "order": 1},
             {"name": "Ada Example", "role": "Keeper", "order": 0,
              "thumbnail": "image://http%3a%2f%2fmedia.example.lan%2fada.jpg%3fapi_key%3dsecret/"},
             {"name": "", "role": "Nobody"}, "junk"],
    "streamdetails": {"video": [{"width": 1920, "height": 800, "codec": "hevc", "hdrtype": "dolbyvision"}],
                      "audio": [{"channels": 8, "codec": "truehd_atmos"}]},
    "file": "http://media.example.lan/stream?api_key=secret",
}


class DetailsTest(unittest.TestCase):
    maxDiff = None

    def test_library_film(self):
        got = d.details(FILM, {}, {}, played=6000)
        self.assertEqual(got, {
            "title": "Harbour Lights", "subtitle": "2019", "plot": "A keeper finds a map.",
            "badges": ["1080p", "HEVC", "Dolby Vision", "TrueHD Atmos", "7.1"],
            "info": [{"kind": "genre", "text": "Drama, Mystery"},
                     {"kind": "date", "text": "2019-03-01"},
                     {"kind": "studio", "text": "Northlight, Harbour Films"},
                     {"kind": "rating", "text": "7.8 (12,345 votes)"},
                     {"kind": "age", "text": "PG-13"},
                     {"kind": "runtime", "text": "1h 52m"},
                     {"kind": "director", "text": "Mara Example"},
                     {"kind": "writer", "text": "Ivo Sample, Lena Draft"},
                     {"kind": "country", "text": "Norway, Iceland"}],
            "cast": [{"name": "Ada Example", "role": "Keeper",
                      "thumb": "image://http%3a%2f%2fmedia.example.lan%2fada.jpg%3fapi_key%3dsecret/"},
                     {"name": "Tom Byway", "role": "Ferryman", "thumb": ""}]})
        public = d.public(got, {})
        self.assertEqual(public["cast"], [{"name": "Ada Example", "role": "Keeper", "photo": ""},
                                          {"name": "Tom Byway", "role": "Ferryman", "photo": ""}])
        self.assertNotIn("api_key", json.dumps(public))
        self.assertNotIn("thumb", json.dumps(public))
        self.assertEqual(d.public(got, {FILM["cast"][1]["thumbnail"]: "/c/omakodi/art/" + "a" * 32 + ".jpg"})["cast"][0]
                         ["photo"], "/c/omakodi/art/" + "a" * 32 + ".jpg")
        self.assertEqual(d.photo_urls(got), [FILM["cast"][1]["thumbnail"]])

    def test_episode(self):
        item = {"type": "episode", "title": "The Tide Turns", "showtitle": "Coastline", "season": 2, "episode": 5,
                "plot": "Storm night.", "firstaired": "2021-10-04", "premiered": "2021-01-01", "year": 2021,
                "rating": 0, "mpaa": "TV-14", "runtime": 0}
        got = d.details(item, {"currentvideostream": {"width": 1280, "height": 720, "codec": "h264"}}, {}, played=2700)
        self.assertEqual(got["subtitle"], "S02E05 · Coastline")
        self.assertEqual(got["info"], [{"kind": "show", "text": "Coastline"},
                                       {"kind": "date", "text": "2021-10-04"},  # aired, not the show's premiere
                                       {"kind": "age", "text": "TV-14"},
                                       {"kind": "runtime", "text": "45m"}])  # Kodi's length when it has none
        self.assertEqual(got["badges"], ["720p", "H.264"])

    def test_youtube_video(self):
        # As the YouTube add-on gives one on Kodi 21: the channel as the
        # artist, a stats line in the plot, a rating from the likes.
        item = {"type": "unknown", "label": "Ten Knots Explained", "title": "Ten Knots Explained",
                "artist": ["Example Sailing"], "genre": [], "year": 2026, "premiered": "2026-09-19",
                "firstaired": "2026-09-19", "rating": 6.088, "votes": "0", "runtime": 847, "cast": [],
                "plot": "[B]Example Sailing[/B][CR][COLOR=ffadd8e6][B]42K Views[/B][/COLOR] | "
                        "[COLOR=ff00ff00][B]2.6K Likes[/B][/COLOR] | [COLOR=ff00ffff][B]371 Comments[/B][/COLOR]"
                        "[CR]Ten knots | 3 likes each.\nhttps://video.example.lan/sailing"}
        live = {"currentvideostream": {"width": 1920, "height": 1080, "codec": "h264"},
                "currentaudiostream": {"channels": 2, "codec": "aac"}}
        got = d.details(item, live, {"VideoPlayer.Votes": "0", "VideoPlayer.Year": "2026"})
        self.assertEqual(got, {
            "title": "Ten Knots Explained", "subtitle": "2026",
            "plot": "Example Sailing\n42K Views\nTen knots | 3 likes each.\nhttps://video.example.lan/sailing",
            "badges": ["1080p", "H.264", "AAC", "2.0"],
            "info": [{"kind": "channel", "text": "Example Sailing"},
                     {"kind": "date", "text": "2026-09-19"},
                     {"kind": "rating", "text": "6.1"},
                     {"kind": "runtime", "text": "14m"}]})

    def test_addon_item_from_the_player_labels(self):
        # An add-on that fills only Kodi's player labels.
        labels = {"VideoPlayer.Plot": "A [I]quiet[/I] harbour.", "VideoPlayer.Artist": "Harbour Channel",
                  "VideoPlayer.Genre": "Documentary / Travel", "VideoPlayer.Premiered": "04-05-2010",
                  "VideoPlayer.Year": "2010", "VideoPlayer.Studio": "Example Studio",
                  "VideoPlayer.Rating": "8.25", "VideoPlayer.Votes": "1,204", "VideoPlayer.Director": "Kai Lens",
                  "VideoPlayer.Writer": "", "VideoPlayer.Tagline": "unused"}
        got = d.details({"type": "unknown", "label": "harbour.mp4"}, {}, labels, played=95)
        self.assertEqual(got, {
            "title": "harbour.mp4", "plot": "A quiet harbour.",
            "info": [{"kind": "channel", "text": "Harbour Channel"},
                     {"kind": "genre", "text": "Documentary, Travel"},
                     {"kind": "date", "text": "04-05-2010"},
                     {"kind": "studio", "text": "Example Studio"},
                     {"kind": "rating", "text": "8.2 (1,204 votes)"},
                     {"kind": "runtime", "text": "1m 35s"},
                     {"kind": "director", "text": "Kai Lens"}]})
        # Only a tagline: it stands in for the plot.
        self.assertEqual(d.details({"label": "x"}, {}, {"VideoPlayer.Tagline": "Just a tagline"})["plot"],
                         "Just a tagline")

    def test_songs_have_no_channel(self):
        got = d.details({"type": "song", "title": "Sea Song", "artist": ["Example Band"], "genre": ["Folk"]}, {}, {})
        self.assertEqual(got["subtitle"], "Example Band")
        self.assertEqual(got["info"], [{"kind": "genre", "text": "Folk"}])

    def test_empty_fields_left_out(self):
        self.assertIsNone(d.details({}, {}))
        self.assertIsNone(d.details(None, None, None))
        self.assertIsNone(d.details({"title": "Only a title", "plot": "  ", "genre": [], "year": 0, "rating": 0,
                                     "cast": []}, {}))
        self.assertEqual(d.details({"plot": "[B][/B]Only a plot"}, None), {"plot": "Only a plot"})

    def test_bounds(self):
        long = "é" * 500
        item = {"title": long, "plot": long * 20, "genre": [long] * 20, "studio": [long] * 5, "year": 99999,
                "firstaired": long, "rating": 11, "votes": "9" * 40, "runtime": 10 ** 9,
                "cast": [{"name": long + str(i), "role": long, "thumbnail": "image://" + "x" * 5000}
                         for i in range(50)]}
        got = d.details(item, {"currentvideostream": {"width": 1920, "height": 1080, "codec": long},
                               "currentaudiostream": {"channels": 2, "codec": long}},
                        {"VideoPlayer.Plot": long, "VideoPlayer.Rating": "nan"})
        self.assertEqual(len(got["plot"]), d.MAX_PLOT)
        self.assertTrue(got["plot"].endswith("…"))
        self.assertEqual(len(got["title"]), d.MAX_TITLE)
        self.assertTrue(all(len(r["text"]) <= d.MAX_INFO for r in got["info"]))
        self.assertEqual([r["kind"] for r in got["info"]], ["genre", "date", "studio"])
        self.assertTrue(all(r["kind"] in d.INFO_KINDS for r in got["info"]))
        self.assertEqual(len(got["cast"]), d.MAX_CAST)
        self.assertTrue(all(len(c["name"]) <= d.MAX_NAME and len(c["role"]) <= d.MAX_NAME and c["thumb"] == ""
                            for c in got["cast"]))
        self.assertLessEqual(len(got["badges"]), d.MAX_BADGES)
        self.assertTrue(all(len(b) <= d.MAX_BADGE for b in got["badges"]))
        # Below the shell's 64 KiB line limit, with room for a full queue.
        self.assertLess(len(json.dumps(d.public(got, {}), ensure_ascii=False).encode()), 32 * 1024)

    def test_duration_and_votes(self):
        self.assertEqual([d.duration(x) for x in (3720, 3600, 600, 597, 59, 0, -5, "60", True)],
                         ["1h 2m", "1h 0m", "10m", "9m 57s", "0m 59s", "", "", "", ""])
        self.assertEqual([d._votes(x) for x in ("1,234", "0", "", "lots", 77, None, "-3")],
                         [1234, 0, 0, 0, 77, 0, 0])


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
                         "Player.GetProperties": {"currentvideostream": {"width": 1280, "height": 720}},
                         "XBMC.GetInfoLabels": {"VideoPlayer.Director": "Kai Lens"}})
        self.assertEqual(d.read_details(kodi, 1, 0), ({"plot": "p", "badges": ["720p"],
                                                       "info": [{"kind": "director", "text": "Kai Lens"}]}, True))
        self.assertEqual([m for m, _ in kodi.calls], ["Player.GetItem", "Player.GetProperties", "XBMC.GetInfoLabels"])
        for method, params in kodi.calls[:2]:
            self.assertEqual(params["playerid"], 1)
            self.assertNotIn("file", params["properties"])
        self.assertEqual(kodi.calls[2][1], {"labels": d.LABELS})

    def test_unusable_answers_give_no_details(self):
        kodi = FakeKodi({"Player.GetItem": OmakodiError("kodi error", "Invalid params", FAILED),
                         "Player.GetProperties": OmakodiError("bad response", "", FAILED),
                         "XBMC.GetInfoLabels": OmakodiError("kodi error", "", FAILED)})
        self.assertEqual(d.read_details(kodi, 1), (None, False))

    def test_lost_connection_and_wrong_password_fail(self):
        for code in (UNREACHABLE, AUTH):
            kodi = FakeKodi({"Player.GetItem": OmakodiError("x", "", code)})
            with self.assertRaises(OmakodiError):
                d.read_details(kodi, 1)


if __name__ == "__main__":
    unittest.main()
