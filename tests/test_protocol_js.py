"""Protocol.js hasLink() against links.extract_url() (ticket 016).

The service answers "no link found" with the JS check; the daemon decides
with the Python one. They must give the same yes/no for any text.
"""

import json
import os
import shutil
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "lib"))

from omakodi.control import ACTIONS  # noqa: E402
from omakodi.links import MAX_URL, extract_url  # noqa: E402

# Loads Protocol.js (minus the QML-only pragma) and answers hasLink() for
# each text in the JSON array on stdin.
RUNNER = r"""
const fs = require("fs"), vm = require("vm")
const src = fs.readFileSync(process.argv[1], "utf8").replace(/^\.pragma library\s*$/m, "")
const ctx = {}
vm.runInNewContext(src, ctx)
const texts = JSON.parse(fs.readFileSync(0, "utf8"))
process.stdout.write(JSON.stringify(texts.map(t => ctx.hasLink(t))))
"""

# Every character Python's \s or JS's \s matches, the ones the class excludes,
# and the non-ASCII ones that case-fold to a letter of "https".
SPECIAL = (
    [chr(c) for c in range(0x110000) if chr(c).isspace() or chr(c) in "\ufeff\u017f\u212a\u0130\u0131"]
    + list("<>\"'.,;!)xX/:")
)

FIXED = [
    "", "just words", "http", "https:", "https:/", "https://", "https://.", "https://)",
    "https://x", "http://x", "HTTP://X", "HtTpS://kodi.example.lan/a?b=c#d",
    "look: https://www.youtube.com/watch?v=aqz-KE-bpKQ.", "(https://example.org/x)",
    '"https://example.org/x"', "'https://example.org'", "<https://example.org>",
    "ftp://example.org", "mailto:someone@example.org", "httpx://example.org",
    "text\nhttps://example.org\nmore", "https:// example.org", "http\u017f://example.org",
    "https://" + "a" * MAX_URL, "https://" + "a" * (MAX_URL - 8),
    "https://" + "a" * (MAX_URL - 8) + "...", "https://" + "a" * (MAX_URL - 7),
    "https://" + "\U0001f600" * (MAX_URL - 8), "https://" + "\U0001f600" * (MAX_URL - 7),
    "https://" + "\U0001f600" * (MAX_URL - 9) + "a.",
]


def sweep():
    for c in SPECIAL:
        yield "https://" + c
        yield "https://" + c + "x"
        yield "https://x" + c
        yield "http" + c + "://x"
        yield c + "https://x"


@unittest.skipUnless(shutil.which("node"), "node is needed to run Protocol.js")
class HasLinkTest(unittest.TestCase):
    def js(self, texts):
        r = subprocess.run(
            ["node", "-e", RUNNER, os.path.join(ROOT, "Protocol.js")],
            input=json.dumps(texts), capture_output=True, text=True, timeout=60,
        )
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def check(self, texts):
        got = self.js(texts)
        for text, answer in zip(texts, got, strict=True):
            with self.subTest(text=text[:60]):
                self.assertEqual(answer, extract_url(text) is not None)

    def test_fixed_cases(self):
        self.check(FIXED)

    def test_every_special_character(self):
        self.check(list(sweep()))

    def test_examples(self):
        self.assertEqual(self.js(["just words", "see https://kodi.example.lan/x"]), [False, True])


# Parses each daemon line in the JSON array on stdin with Protocol.parse().
PARSE_RUNNER = RUNNER.replace("ctx.hasLink(t)", "ctx.parse(t)")


@unittest.skipUnless(shutil.which("node"), "node is needed to run Protocol.js")
class StateInputTest(unittest.TestCase):
    """The state's ``input`` (ticket 019) reaches the QML as known fields only."""

    def parse(self, inputs):
        lines = [json.dumps({"type": "state", "reachable": True, "input": i}) for i in inputs]
        r = subprocess.run(
            ["node", "-e", PARSE_RUNNER, os.path.join(ROOT, "Protocol.js")],
            input=json.dumps(lines), capture_output=True, text=True, timeout=60,
        )
        self.assertEqual(r.returncode, 0, r.stderr)
        return [m["input"] for m in json.loads(r.stdout)]

    def test_input(self):
        got = self.parse([
            None,
            {"type": "keyboard", "title": "Search", "value": "the w"},
            {"type": "password", "title": "Login", "value": ""},
            {"type": "numericpassword"},
            {"title": 7, "value": ["x"], "extra": "dropped"},
            "keyboard",
            {"type": "keyboard", "title": "t" * 400},
        ])
        self.assertEqual(got[:5], [
            None,
            {"type": "keyboard", "title": "Search", "value": "the w", "hidden": False},
            {"type": "password", "title": "Login", "value": "", "hidden": True},
            {"type": "numericpassword", "title": "", "value": "", "hidden": True},
            {"type": "keyboard", "title": "", "value": "", "hidden": False},
        ])
        self.assertIsNone(got[5])
        self.assertEqual(len(got[6]["title"]), 300)


# Loads a .pragma library file and prints the JSON of one expression.
EVAL_RUNNER = r"""
const fs = require("fs"), vm = require("vm")
const src = fs.readFileSync(process.argv[1], "utf8").replace(/^\.pragma library\s*$/m, "")
const ctx = {}
vm.runInNewContext(src, ctx)
process.stdout.write(JSON.stringify(vm.runInContext(process.argv[2], ctx)))
"""


class EvalJs:
    def js(self, name, expr):
        r = subprocess.run(["node", "-e", EVAL_RUNNER, os.path.join(ROOT, name), expr],
                           capture_output=True, text=True, timeout=60, env={**os.environ, "TZ": "UTC"})
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)


@unittest.skipUnless(shutil.which("node"), "node is needed to run the JS files")
class ActionsTest(EvalJs, unittest.TestCase):
    """The shell knows the same remote actions as the daemon (ticket 020)."""

    def test_protocol_actions_match_the_daemon(self):
        self.assertEqual(sorted(self.js("Protocol.js", "ACTIONS")), sorted(ACTIONS))

    def test_every_remote_key_is_an_action(self):
        mapped = self.js("RemoteKeys.js", "Object.values(BY_KEY).concat(Object.values(BY_TEXT))")
        self.assertLessEqual(set(mapped), set(ACTIONS))

    def test_next_and_previous_keys(self):
        self.assertEqual(self.js("RemoteKeys.js", '[lookup(0, ".", 0), lookup(0, ",", 0)]'),
                         [{"control": "next"}, {"control": "previous"}])


@unittest.skipUnless(shutil.which("node"), "node is needed to run the JS files")
class NowPlayingJsTest(EvalJs, unittest.TestCase):
    """The seek bar's numbers (ticket 023)."""

    def test_rewind_and_fast_forward_keys(self):
        self.assertEqual(self.js("RemoteKeys.js", '[lookup(0, "<", 0), lookup(0, ">", 0x02000000)]'),
                         [{"control": "rewind"}, {"control": "fastforward"}])

    def test_speed_in_the_state(self):
        expr = """[4, -2, 0, 1.5, 999, "2", undefined].map(function(s) {
          return parse(JSON.stringify({type: "state", playing: {title: "x", speed: s, paused: s === 0}})).playing.speed
        })"""
        self.assertEqual(self.js("Protocol.js", expr), [4, -2, 0, 1, 1, 1, 1])

    def test_art_only_from_the_cache(self):
        good = "/home/someone/.cache/omakodi/art/" + "0123456789abcdef" * 2 + ".jpg"
        bad = ["", "http://media.example.lan/x.jpg", "file:///tmp/x.jpg", "relative/omakodi/art/x.jpg",
               "/home/someone/.cache/omakodi/art/../../.ssh/" + "0" * 32 + ".jpg",
               "/home/someone/.cache/omakodi/art/" + "0" * 32 + ".svg",
               "/home/someone/.cache/omakodi/art/notahash.png", good + "\n", 7, None]
        expr = "%s.map(function(a) { return parse(JSON.stringify({type: 'state', playing: {art: a}})).playing.art })"
        self.assertEqual(self.js("Protocol.js", expr % json.dumps([good] + bad)), [good] + [""] * len(bad))

    def test_queue_in_the_state(self):
        expr = """[
          {position: 1, start: 0, total: 3, items: [{title: "One", subtitle: ""}, {title: "Two"}, {x: 1}]},
          {position: 1, start: 0, total: 1, items: [{title: "A"}, {title: "B"}]},
          {position: -5, start: "x", items: []},
          {position: 1}, null, "queue"
        ].map(function(q) { return parse(JSON.stringify({type: "state", queue: q})).queue })"""
        self.assertEqual(self.js("Protocol.js", expr), [
            {"position": 1, "start": 0, "total": 3, "items": [
                {"title": "One", "subtitle": ""}, {"title": "Two", "subtitle": ""}, {"title": "", "subtitle": ""}]},
            {"position": 1, "start": 0, "total": 2, "items": [
                {"title": "A", "subtitle": ""}, {"title": "B", "subtitle": ""}]},
            {"position": 0, "start": 0, "total": 0, "items": []},
            None, None, None])
        many = self.js("Protocol.js", "parse(JSON.stringify({type: 'state', queue: {position: 0, start: 0, total: 500,"
                                      " items: Array(150).fill({title: 'x'.repeat(350)})}})).queue")
        self.assertEqual((len(many["items"]), len(many["items"][0]["title"]), many["total"]), (100, 300, 500))

    def test_details_in_the_state(self):
        expr = """[
          {plot: "One\\ntwo", genres: ["Drama", 3, "", "Mystery"], year: 2019, studio: "North",
           rating: "7.8", cast: ["Ada"], badges: ["4K", "HDR10"], extra: "dropped"},
          {year: 1.5, rating: "11.0", genres: "Drama", cast: null},
          {year: 2019.0, rating: "10.0"}, {rating: "<b>"}, null, [], "details"
        ].map(function(d) { return parse(JSON.stringify({type: "state", details: d})).details })"""
        empty = {"plot": "", "genres": [], "year": 0, "studio": "", "rating": "", "cast": [], "badges": []}
        self.assertEqual(self.js("Protocol.js", expr), [
            {"plot": "One\ntwo", "genres": ["Drama", "Mystery"], "year": 2019, "studio": "North",
             "rating": "7.8", "cast": ["Ada"], "badges": ["4K", "HDR10"]},
            empty, {**empty, "year": 2019, "rating": "10.0"}, empty, None, None, None])
        big = self.js("Protocol.js", "parse(JSON.stringify({type: 'state', details: {plot: 'x'.repeat(5000),"
                                     " cast: Array(50).fill('y'.repeat(99)), badges: Array(9).fill('z'.repeat(30)),"
                                     " genres: Array(9).fill('g'.repeat(50))}})).details")
        self.assertEqual((len(big["plot"]), len(big["cast"]), len(big["cast"][0]), len(big["badges"]),
                          len(big["badges"][0]), len(big["genres"]), len(big["genres"][0])),
                         (3000, 10, 60, 4, 20, 5, 40))

    def test_details_keys(self):
        self.assertEqual(self.js("RemoteKeys.js", '[lookup(0, "d", 0), lookup(0, "D", 0x02000000),'
                                 ' lookup(0, "d", 0x04000000)]'),
                         [{"details": True}, {"wholePlot": True}, None])

    def test_audio_in_the_state(self):
        expr = """[
          {current: 1, tracks: [{index: 0, name: "Stereo", language: "eng", codec: "AAC", channels: "Stereo"},
                                {index: 1, extra: "x"}, {index: 1}, {index: -1}, {index: 1.5}, "junk"]},
          {current: 7, tracks: [{index: 0}]}, {current: 0, tracks: []}, {tracks: "x"}, null
        ].map(function(a) { return parse(JSON.stringify({type: "state", audio: a})).audio })"""
        self.assertEqual(self.js("Protocol.js", expr), [
            {"current": 1, "tracks": [
                {"index": 0, "name": "Stereo", "language": "eng", "codec": "AAC", "channels": "Stereo"},
                {"index": 1, "name": "", "language": "", "codec": "", "channels": ""}]},
            {"current": -1, "tracks": [{"index": 0, "name": "", "language": "", "codec": "", "channels": ""}]},
            None, None, None])
        many = self.js("Protocol.js", "parse(JSON.stringify({type: 'state', audio: {current: 0, tracks:"
                                      " Array(50).fill(0).map(function(_, i) { return {index: i, name: 'n'.repeat(200)} })"
                                      "}})).audio")
        self.assertEqual((len(many["tracks"]), len(many["tracks"][0]["name"])), (32, 100))

    def test_audio_and_player_info_keys(self):
        self.assertEqual(self.js("RemoteKeys.js", '[lookup(0, "a", 0), lookup(0, "I", 0x02000000),'
                                 ' lookup(0, "i", 0), lookup(0, "a", 0x08000000)]'),
                         [{"audioList": True}, {"control": "playerinfo"}, {"control": "info"}, None])

    def test_more_key(self):
        self.assertEqual(self.js("RemoteKeys.js", '[lookup(0, "n", 0), lookup(0, "N", 0x02000000)]'),
                         [{"more": True}, None])

    def test_power_in_the_state(self):
        expr = """[{state: "off", reboot: true, shutdown: 1}, {state: "gone"}, null, "on"]
          .map(function(p) { return parse(JSON.stringify({type: "state", power: p})).power })"""
        self.assertEqual(self.js("Protocol.js", expr), [
            {"state": "off", "reboot": True, "shutdown": False},
            {"state": "on", "reboot": False, "shutdown": False}, None, None])

    def test_wake_in_the_state_and_its_key(self):
        expr = """[true, false, "true", 1, null, undefined]
          .map(function(w) { return parse(JSON.stringify({type: "state", wake: w})).wake })"""
        self.assertEqual(self.js("Protocol.js", expr), [True, False, False, False, False, False])
        self.assertEqual(self.js("RemoteKeys.js", '[lookup(0, "w", 0), lookup(0, "W", 0x02000000),'
                                 ' lookup(0, "w", 0x04000000)]'),
                         [{"wake": True}, None, None])

    def test_volume_keys_in_the_state_and_the_soundbar_keys(self):
        expr = """["tv", "kodi", "unknown", "soundbar", null, 1]
          .map(function(v) { return parse(JSON.stringify({type: "state", volumeKeys: v})).volumeKeys })"""
        self.assertEqual(self.js("Protocol.js", expr), ["tv", "kodi", "unknown", "unknown", "unknown", "unknown"])
        self.assertEqual(self.js("RemoteKeys.js", '[lookup(0, "9", 0), lookup(0, "0", 0), lookup(0, "M", 0x02000000),'
                                 ' lookup(0, "m", 0), lookup(0, "9", 0x04000000)]'),
                         [{"control": "soundbardown"}, {"control": "soundbarup"}, None,
                          {"control": "mute"}, None])

    def test_youtube_mode_in_the_state(self):
        expr = """[{mode: "sendtokodi-only", from: "remote", avoidUntil: 1795000000.7, box: "kodi.example.lan"},
                   {mode: "fast", from: "elsewhere", avoidUntil: -5}, {avoidUntil: "soon"}, null, "smart"]
          .map(function(y) { return parse(JSON.stringify({type: "state", youtube: y})).youtube })"""
        self.assertEqual(self.js("Protocol.js", expr), [
            {"mode": "sendtokodi-only", "from": "remote", "avoidUntil": 1795000000, "box": "kodi.example.lan"},
            {"mode": "smart", "from": "config", "avoidUntil": 0, "box": ""},
            {"mode": "smart", "from": "config", "avoidUntil": 0, "box": ""}, None, None])
        from omakodi.config import YOUTUBE_MODES
        self.assertEqual(sorted(self.js("Protocol.js", "YOUTUBE_MODES")), sorted(YOUTUBE_MODES))

    def test_soundbar_key(self):
        self.assertEqual(self.js("RemoteKeys.js", '[lookup(0, "s", 0), lookup(0, "S", 0x02000000),'
                                 ' lookup(0, "s", 0x04000000)]'),
                         [{"control": "soundbaron"}, {"settings": True}, None])

    def test_power_key_only_opens_the_menu(self):
        self.assertEqual(self.js("RemoteKeys.js", '[lookup(0, "P", 0x02000000), lookup(0, "p", 0)]'),
                         [{"powerMenu": True}, {"link": "play"}])
        mapped = self.js("RemoteKeys.js", "Object.values(BY_KEY).concat(Object.values(BY_TEXT))")
        self.assertFalse({"reboot", "shutdown"} & set(mapped))  # no key turns the box off

    def test_power_menu_asks_again(self):
        self.assertEqual(self.js("PowerMenu.js", '[items(null), items({reboot: true, shutdown: true}),'
                                 ' items({reboot: false, shutdown: true}), items({reboot: "yes"})]'),
                         [["powermenu", "soundbaron"], ["powermenu", "soundbaron", "reboot", "shutdown"],
                          ["powermenu", "soundbaron", "shutdown"], ["powermenu", "soundbaron"]])
        got = self.js("PowerMenu.js", """[
          pick("powermenu", ""), pick("soundbaron", ""), pick("soundbaron", "reboot"),
          pick("reboot", ""), pick("reboot", "reboot"),
          pick("shutdown", ""), pick("shutdown", "shutdown"),
          pick("shutdown", "reboot"), pick("reboot", "shutdown"),
          pick("home", ""), pick("home", "home")]""")
        self.assertEqual(got, [
            {"send": "powermenu", "armed": ""}, {"send": "soundbaron", "armed": ""}, {"send": "soundbaron", "armed": ""},
            {"send": "", "armed": "reboot"}, {"send": "reboot", "armed": ""},
            {"send": "", "armed": "shutdown"}, {"send": "shutdown", "armed": ""},
            {"send": "", "armed": "shutdown"}, {"send": "", "armed": "reboot"},  # the other row: ask again
            {"send": "", "armed": ""}, {"send": "", "armed": ""}])

    def test_queue_key(self):
        self.assertEqual(self.js("RemoteKeys.js", '[lookup(0, "u", 0), lookup(0, "u", 0x04000000)]'),
                         [{"queueList": True}, None])

    def test_ends_at(self):
        # 2026-11-18 02:15:00 UTC plus 47:20 - 21:53
        self.assertEqual(self.js("Format.js", "endsAt(2840 - 1313, Date.UTC(2026, 10, 18, 2, 15))"), "02:40")
        self.assertEqual(self.js("Format.js", "endsAt(-5, Date.UTC(2026, 10, 18, 23, 59, 30))"), "23:59")

    def test_live_position(self):
        self.assertEqual(self.js("Format.js", "[livePosition(100, 3000, 1, 3000), livePosition(100, 3000, 4, 0),"
                                 " livePosition(100, 3000, 0, 3000), livePosition(100, 60000, -2, 3000),"
                                 " livePosition(2990, 30000, 1, 3000), livePosition(100, -500, 1, 3000)]"),
                         [103, 112, 100, 0, 3000, 100])



@unittest.skipUnless(shutil.which("node"), "node is needed to run the JS files")
class ShortcutsJsTest(EvalJs, unittest.TestCase):
    """The shortcut strip's shell side (ticket 041)."""

    def test_icons_match_the_daemon(self):
        from omakodi.shortcuts import ICONS
        self.assertEqual(self.js("Shortcuts.js", "names()"), list(ICONS))
        points = self.js("Shortcuts.js", "ICONS.map(function(p) { return p[1] })")
        self.assertEqual(len(set(points)), len(points))
        self.assertTrue(all(0xF0001 <= p <= 0xF1AF0 for p in points))  # Material Design Icons in the Nerd Font
        self.assertEqual(self.js("Shortcuts.js", '[glyph("home"), glyph("rocket"), buttonGlyph({icon: "", auto: "tv"}),'
                                 ' buttonGlyph({icon: "soccer", auto: "tv"}), buttonGlyph(null)]'),
                         [chr(0xF02DC), chr(0xF0256), chr(0xF0502), chr(0xF04B8), chr(0xF0256)])

    def test_typed_paths_like_the_daemon(self):
        from omakodi.shortcuts import MAX_PATH, normalize
        texts = ["", " ", "plugin.video.youtube", " plugin://plugin.video.youtube ", "PLUGIN://x.y",
                 "plugin://plugin.video.youtube/", "plugin://a?b", "plugin://a#b", "videodb://movies/titles/",
                 "smb://nas.example.lan/My Films/", "script.example.tool", "Plugin.Audio.X", "youtube", "a.",
                 ".a", "a..b", "a.b-c", "a-b.c", "x\n://y", "a.b\n", "\ufeffa.b", "\x85a.b\x1c",
                 "\u00a0plugin.video.x\u3000", "plugın.video.x", "p\u0130ugin://x", "\u212aodi.x",
                 "smb://" + "a" * (MAX_PATH - 6), "smb://" + "a" * (MAX_PATH - 5),
                 "smb://" + "\U0001f600" * (MAX_PATH - 6), "smb://" + "\U0001f600" * (MAX_PATH - 5)]
        texts += [c + "a.b" + c for c in "\t\x0b\x0c\x1f\x7f\x9f\u2028\u200b\u180e"]
        got = self.js("Shortcuts.js", "%s.map(normalize)" % json.dumps(texts))
        for text, answer in zip(texts, got, strict=True):
            with self.subTest(text=text[:40]):
                self.assertEqual(answer, normalize(text) or "")

    def test_icon_page_moves(self):
        # Kodi's tile (0), then 72 icons in rows of 8
        moves = [(0, 1, 0), (0, 0, 1), (0, -1, 0), (0, 0, -1), (1, -1, 0), (1, 1, 0), (3, 0, -1), (3, 0, 1),
                 (10, 0, -1), (72, 0, 1), (72, 1, 0), (68, 0, 1), (9, -1, 0)]
        got = self.js("Shortcuts.js", "%s.map(function(m) { return iconMove(m[0], m[1], m[2], 8, 72) })"
                      % json.dumps(moves))
        self.assertEqual(got, [1, 1, 0, 0, 0, 2, 0, 11, 2, 72, 72, 68, 8])

    def test_extract_link_like_the_daemon(self):
        texts = ["look: https://www.youtube.com/watch?v=aqz-KE-bpKQ.", "nothing", "(https://example.org/x)",
                 "a https://kodi.example.lan/a?b=c#d b"]
        got = self.js("Protocol.js", "%s.map(extractLink)" % json.dumps(texts))
        self.assertEqual(got, [extract_url(t) or "" for t in texts])

    def test_shortcuts_in_the_state(self):
        art = "/home/someone/.cache/omakodi/art/" + "a" * 32 + ".png"
        good = {"label": "Movies", "sendLink": False, "icon": "film", "art": art, "auto": "movie",
                "custom": True, "typed": ""}
        junk = {"label": 5, "sendLink": "yes", "icon": "Bad Icon", "art": "https://x/y.png", "auto": None,
                "custom": 1, "typed": None}
        expr = """[{box: "kodi.example.lan", buttons: %s}, {buttons: [1, 2]}, null, {buttons: "x"}]
          .map(function(s) { return parse(JSON.stringify({type: "state", shortcuts: s})).shortcuts })""" % (
            json.dumps([good, junk, good, good, {}]))
        got = self.js("Protocol.js", expr)
        blank = {"label": "", "sendLink": False, "icon": "", "art": "", "auto": "folder", "custom": False,
                 "typed": ""}
        self.assertEqual(got[0], {"box": "kodi.example.lan", "buttons": [good, blank, good, good, blank]})
        self.assertEqual(got[1:], [None, None, None])

    def test_picker_lines(self):
        expr = """[{type: "picker", seq: 4, title: "YouTube", crumb: "YouTube", folder: true, depth: 2,
                    status: "ready", error: "", items: [{label: "Trending", detail: "", browse: true}, 7]},
                   {type: "picker", status: "odd", seq: -3, items: "x"}].map(function(p) {
                     return parse(JSON.stringify(p)) })"""
        self.assertEqual(self.js("Protocol.js", expr), [
            {"type": "picker", "seq": 4, "title": "YouTube", "crumb": "YouTube", "folder": True, "depth": 2,
             "status": "ready", "error": "", "items": [{"label": "Trending", "detail": "", "browse": True},
                                                       {"label": "", "detail": "", "browse": False}]},
            {"type": "picker", "seq": 0, "title": "", "crumb": "", "folder": False, "depth": 1,
             "status": "failed", "error": "", "items": []}])

    def test_strip_keys(self):
        self.assertEqual(self.js("RemoteKeys.js", '[lookup(0, "1", 0), lookup(0, "5", 0), lookup(0, "6", 0),'
                                 ' lookup(0, "e", 0), lookup(0, "e", 0x04000000), stripSlot("3"), stripSlot("0"),'
                                 ' stripSlot("12")]'),
                         [{"shortcut": 0}, {"shortcut": 4}, None, {"editStrip": True}, None, 2, -1, -1])


if __name__ == "__main__":
    unittest.main()
