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


if __name__ == "__main__":
    unittest.main()
