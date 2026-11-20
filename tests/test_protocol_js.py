"""Protocol.js hasLink() against links.extract_url() (ticket 016).

The service answers "no link found" with the JS check; the daemon decides
with the Python one. They must give the same yes/no for any text.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "lib"))

from omakodi.control import ACTIONS  # noqa: E402
from omakodi.links import MAX_URL, extract_url  # noqa: E402
from omakodi.audio import tracks  # noqa: E402
from omakodi.nowplaying import MAX_TEXT  # noqa: E402

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

    def test_keyboard_key(self):
        self.assertEqual(self.js("RemoteKeys.js", '[lookup(0, "k", 0), lookup(0, "k", 0x04000000), lookup(0, "K", 0x02000000)]'),
                         [{"keyboard": True}, None, None])

    def test_action_row_in_the_phone_order(self):
        # Home is on the strip; the context menu is a long press of OK, a right click or c.
        self.assertEqual(self.js("RemoteKeys.js", "ACTION_ROW"), ["audio", "fullscreen", "info", "keyboard", "playerinfo"])
        self.assertEqual(self.js("RemoteKeys.js", '[lookup(0, "c", 0), lookup(0, "h", 0)]'),
                         [{"control": "context"}, {"control": "home"}])

    def test_held_keys_repeat_like_a_remote(self):
        self.assertEqual(self.js("RemoteKeys.js", "[REPEAT_DELAY, REPEAT_INTERVAL, LONG_PRESS]"), [400, 110, 500])
        self.assertEqual(self.js("RemoteKeys.js", "repeatTimes(1000)"), [400, 510, 620, 730, 840, 950])
        self.assertEqual(self.js("RemoteKeys.js", "repeatTimes(399)"), [])
        held = self.js("RemoteKeys.js", "HELD_REPEATS")
        self.assertLessEqual(set(held), set(ACTIONS))
        self.assertEqual(self.js("RemoteKeys.js", "HELD_REPEATS.map(repeats).concat("
                                 "['select', 'mute', 'back', 'osd', 'playpause', ''].map(repeats))"),
                         [True] * len(held) + [False] * 6)
        self.assertEqual(sorted(held), sorted(["up", "down", "left", "right", "volup", "voldown"]))

    def test_soundbar_keys_and_mute_send_once_per_press(self):
        # Ticket 050: held, the soundbar's steps and mute send once (the
        # keyboard's auto-repeats are dropped); Kodi's volume and the arrows repeat.
        once = ["soundbarup", "soundbardown", "mute"]
        self.assertEqual(sorted(self.js("RemoteKeys.js", "ONCE_PER_PRESS")), sorted(once))
        self.assertEqual(self.js("RemoteKeys.js", "%s.map(repeats)" % json.dumps(once)), [False] * 3)
        self.assertEqual(self.js("RemoteKeys.js", "%s.map(oncePerPress)" % json.dumps(once)), [True] * 3)
        self.assertEqual(self.js("RemoteKeys.js", "HELD_REPEATS.map(oncePerPress)"), [False] * 6)
        self.assertEqual(self.js("RemoteKeys.js", "['up', 'volup', 'voldown', 'select'].map(oncePerPress)"),
                         [False] * 4)

    def test_the_panel_drops_held_repeats_of_once_per_press_keys(self):
        with open(os.path.join(ROOT, "Panel.qml"), encoding="utf-8") as f:
            panel = f.read()
        start = panel.index("  function send(action, isRepeat) {")
        body = panel[start:panel.index("\n  }\n", start)]
        self.assertIn("if (isRepeat === true && RemoteKeys.oncePerPress(action)) return", body)
        self.assertLess(body.index("oncePerPress"), body.index("service.key("))

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
        photo = "/home/someone/.cache/omakodi/art/" + "a" * 32 + ".jpg"
        expr = """[
          {title: "Harbour Lights", subtitle: "2019", plot: "One\\ntwo", badges: ["4K", 3, "", "HEVC"],
           info: [{kind: "genre", text: "Drama"}, {kind: "secret", text: "x"}, {kind: "date", text: ""},
                  {kind: "rating", text: 7}, "junk", {kind: "runtime", text: "1h 52m", extra: 1}],
           cast: [{name: "Ada", role: "Keeper", photo: "%s"}, {name: "Tom", photo: "http://media.example.lan/x.jpg"},
                  {name: ""}, {role: "Nobody"}, "junk"], extra: "dropped"},
          {info: "Drama", cast: null, badges: {}},
          null, [], "details"
        ].map(function(d) { return parse(JSON.stringify({type: "state", details: d})).details })""" % photo
        empty = {"title": "", "subtitle": "", "plot": "", "plotStyles": [], "badges": [], "info": [], "cast": []}
        self.assertEqual(self.js("Protocol.js", expr), [
            {"title": "Harbour Lights", "subtitle": "2019", "plot": "One\ntwo", "plotStyles": [],
             "badges": ["4K", "HEVC"],
             "info": [{"kind": "genre", "text": "Drama"}, {"kind": "runtime", "text": "1h 52m"}],
             "cast": [{"name": "Ada", "role": "Keeper", "photo": photo}, {"name": "Tom", "role": "", "photo": ""}]},
            empty, None, None, None])
        big = self.js("Protocol.js", "parse(JSON.stringify({type: 'state', details: {plot: 'x'.repeat(9000),"
                                     " title: 't'.repeat(400), badges: Array(9).fill('z'.repeat(30)),"
                                     " info: Array(30).fill({kind: 'genre', text: 'g'.repeat(500)}),"
                                     " cast: Array(50).fill({name: 'y'.repeat(99), role: 'r'.repeat(99)})}})).details")
        self.assertEqual((len(big["plot"]), len(big["title"]), len(big["badges"]), len(big["badges"][0]),
                          len(big["info"]), len(big["info"][0]["text"]), len(big["cast"]), len(big["cast"][0]["name"]),
                          len(big["cast"][0]["role"])),
                         (5000, 300, 5, 20, 11, 300, 20, 60, 60))

    def test_details_plot_styles(self):
        # Ticket 052: stretches of the plot, in order, not overlapping, a colour only "#rrggbb".
        from omakodi import details as detailsmod
        self.assertEqual(self.js("Protocol.js", "MAX_STYLES"), detailsmod.MAX_STYLES)
        expr = """parse(JSON.stringify({type: "state", details: {plot: "0123456789", plotStyles: [
          {from: 0, to: 2, bold: true},
          {from: 1, to: 3, italic: true},
          {from: 2, to: 4, color: "#ADD8E6"},
          {from: 3, to: 4, color: "#add8e6", bold: "yes"},
          {from: 4, to: 5, color: "red"},
          {from: 5, to: 6, color: "#ff0000;font-size:99px"},
          {from: 6, to: 6, bold: true},
          {from: 7.5, to: 8, bold: true},
          {from: "7", to: 8, bold: true},
          null, "junk", [],
          {from: 7, to: 99, italic: true, extra: "<b>"}
        ]}})).details.plotStyles"""
        self.assertEqual(self.js("Protocol.js", expr), [
            {"from": 0, "to": 2, "bold": True, "italic": False, "color": ""},
            {"from": 3, "to": 4, "bold": False, "italic": False, "color": "#add8e6"},
            {"from": 7, "to": 10, "bold": False, "italic": True, "color": ""}])
        many = self.js("Protocol.js", "parse(JSON.stringify({type: 'state', details: {plot: 'x'.repeat(900), "
                                      "plotStyles: Array.from({length: 400}, (_, i) => ({from: i * 2, to: i * 2 + 1,"
                                      " bold: true}))}})).details.plotStyles.length")
        self.assertEqual(many, 200)
        self.assertEqual(self.js("Protocol.js", "parse(JSON.stringify({type: 'state', details: {plot: 'x',"
                                                " plotStyles: {from: 0, to: 1, bold: true}}})).details.plotStyles"),
                         [])
        # What the daemon makes passes as it is.
        text, styles = detailsmod._plot("[B]Big[/B] [COLOR=ffadd8e6]\U0001f600 blue[/COLOR] [I]it[/I]")
        got = self.js("Protocol.js", "parse(%s).details.plotStyles" % json.dumps(json.dumps(
            {"type": "state", "details": {"plot": text, "plotStyles": styles}})))
        self.assertEqual(got, [{"bold": False, "italic": False, "color": "", **s} for s in styles])

    def test_details_info_kinds_and_icons(self):
        from omakodi import details as detailsmod
        self.assertEqual(self.js("Protocol.js", "INFO_KINDS"), list(detailsmod.INFO_KINDS))
        icons = self.js("NowPlaying.js", "[%s].map(infoIcon)" % ", ".join(
            json.dumps(k) for k in detailsmod.INFO_KINDS + ("unknown",)))
        self.assertEqual(len(set(icons[:-1])), len(detailsmod.INFO_KINDS))  # one icon each
        self.assertTrue(all(0xF0001 <= c <= 0xF1AF0 for c in icons))  # Nerd Font's Material Design range
        self.assertEqual(icons[-1], 0xF02FD)

    def test_details_keys(self):
        self.assertEqual(self.js("RemoteKeys.js", '[lookup(0, "d", 0), lookup(0, "D", 0x02000000),'
                                 ' lookup(0, "d", 0x04000000)]'),
                         [{"details": True}, None, None])  # D left with 046: the whole plot always shows

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

    def test_now_playing_key(self):
        self.assertEqual(self.js("RemoteKeys.js", '[lookup(0, "n", 0), lookup(0, "N", 0x02000000)]'),
                         [{"nowPlaying": True}, None])

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
        expr = """[true, false, "false", 0, null, undefined]
          .map(function(w) { return parse(JSON.stringify({type: "state", wakeOnLan: w})).wakeOnLan })"""
        self.assertEqual(self.js("Protocol.js", expr), [True, False, True, True, True, True])  # only false hides Wake up

    def test_volume_keys_in_the_state_and_the_soundbar_keys(self):
        expr = """["tv", "kodi", "unknown", "soundbar", null, 1]
          .map(function(v) { return parse(JSON.stringify({type: "state", volumeKeys: v})).volumeKeys })"""
        self.assertEqual(self.js("Protocol.js", expr), ["tv", "kodi", "unknown", "unknown", "unknown", "unknown"])
        self.assertEqual(self.js("RemoteKeys.js", '[lookup(0, "9", 0), lookup(0, "0", 0), lookup(0, "M", 0x02000000),'
                                 ' lookup(0, "m", 0), lookup(0, "9", 0x04000000)]'),
                         [{"control": "soundbardown"}, {"control": "soundbarup"}, {"menu": True},
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

    def test_power_menu_rows_in_the_phone_order(self):
        got = self.js("PowerMenu.js", """[items(null), items(null, false),
          items({state: "on", reboot: true, shutdown: true}, true),
          items({state: "on", reboot: false, shutdown: true}), items({reboot: "yes"}, false)]""")
        self.assertEqual(got, [
            ["wake", "soundbaron", "powermenu"],  # Kodi isn't answering: Wake up is how it comes back
            ["soundbaron", "powermenu"],  # wakeOnLan: false
            ["wake", "soundbaron", "powermenu", "reboot", "shutdown"],
            ["wake", "soundbaron", "powermenu", "shutdown"],
            ["soundbaron", "powermenu"]])
        self.assertEqual(self.js("PowerMenu.js", """[
          [0, 1, 2, 3, 4].map(function(at) { return dividerAbove(["wake", "soundbaron", "powermenu", "reboot", "shutdown"], at) }),
          [0, 1, 2].map(function(at) { return dividerAbove(["soundbaron", "powermenu", "shutdown"], at) }),
          [0, 1].map(function(at) { return dividerAbove(["soundbaron", "powermenu"], at) })]"""),
                         [[False, False, False, True, False], [False, False, True], [False, False]])

    def test_power_menu_picks_and_the_dialog(self):
        got = self.js("PowerMenu.js", """[pick("wake"), pick("soundbaron"), pick("powermenu"),
          pick("reboot"), pick("shutdown"), pick("home")]""")
        self.assertEqual(got, [
            {"send": "wake", "ask": ""}, {"send": "soundbaron", "ask": ""}, {"send": "powermenu", "ask": ""},
            {"send": "", "ask": "reboot"}, {"send": "", "ask": "shutdown"}, {"send": "", "ask": ""}])
        self.assertEqual(self.js("PowerMenu.js", '[ask("reboot"), ask("shutdown"), ask("wake")]'),
                         [{"action": "reboot", "at": 0}, {"action": "shutdown", "at": 0}, None])
        # Runs keys through the dialog: [the dialog after each, what was sent].
        flow = """function run(action, keys) {
            var d = ask(action), sent = [], seen = []
            keys.forEach(function(k) { var n = dialogKey(d, k); d = n.dialog; seen.push(d); if (n.send) sent.push(n.send) })
            return [seen, sent]
          }; """
        self.assertEqual(self.js("PowerMenu.js", flow + 'run("reboot", ["enter"])'),
                         [[None], []])  # starts on Cancel: Enter at once sends nothing
        self.assertEqual(self.js("PowerMenu.js", flow + 'run("reboot", ["right", "enter"])'),
                         [[{"action": "reboot", "at": 1}, None], ["reboot"]])
        self.assertEqual(self.js("PowerMenu.js", flow + 'run("shutdown", ["tab", "left", "enter"])'),
                         [[{"action": "shutdown", "at": 1}, {"action": "shutdown", "at": 0}, None], []])
        self.assertEqual(self.js("PowerMenu.js", flow + 'run("shutdown", ["right", "escape"])'),
                         [[{"action": "shutdown", "at": 1}, None], []])
        self.assertEqual(self.js("PowerMenu.js", flow + 'run("shutdown", ["confirm"])'), [[None], ["shutdown"]])
        self.assertEqual(self.js("PowerMenu.js", flow + 'run("reboot", ["right", "cancel"])'),
                         [[{"action": "reboot", "at": 1}, None], []])
        self.assertEqual(self.js("PowerMenu.js", flow + 'run("reboot", ["x", "right", "right", "enter", "enter"])'),
                         [[{"action": "reboot", "at": 0}, {"action": "reboot", "at": 1}, {"action": "reboot", "at": 1},
                           None, None], ["reboot"]])  # once: the dialog is gone after it
        self.assertEqual(self.js("PowerMenu.js", '[dialogKey(null, "confirm"), dialogKey({action: "home", at: 1}, "enter")]'),
                         [{"dialog": None, "send": ""}, {"dialog": None, "send": ""}])

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



@unittest.skipUnless(shutil.which("node"), "node is needed to run the JS files")
class KodiInputJsTest(EvalJs, unittest.TestCase):
    """The dialog for Kodi's keyboard (ticket 047): what it shows and what it sends."""

    def test_same_limit_as_the_daemon(self):
        self.assertEqual(self.js("KodiInput.js", "MAX_TEXT"), MAX_TEXT)
        self.assertEqual(self.js("Protocol.js", "MAX_TEXT"), MAX_TEXT)

    def test_title_dots_and_start_text(self):
        got = self.js("KodiInput.js", """[
            title({title: "Search"}, "Send text to Kodi"), title({title: ""}, "Send text to Kodi"),
            title(null, "Send text to Kodi"), title({title: 7}, "F"),
            hidden({hidden: true}), hidden({hidden: false}), hidden(null),
            startText({value: "the w", hidden: false}), startText({value: "example-secret", hidden: true}),
            startText({value: 5}), startText(null), startText({value: "x".repeat(400)}).length]""")
        self.assertEqual(got, ["Search", "Send text to Kodi", "Send text to Kodi", "F",
                               True, False, False, "the w", "", "", "", 300])

    def test_paste(self):
        got = self.js("KodiInput.js", """[
            paste("the wire", 4, 8, "big sleep"), paste("", 0, 0, "a\\r\\nb\\nc"),
            paste("abc", 3, 3, "def"), paste("abc", 2, 0, "X"), paste("abc", -5, 99, "z"),
            paste("abc", 1, 1, ""), paste("x".repeat(298), 298, 298, "12345").cursor,
            paste("x".repeat(300), 0, 0, "y").text.length]""")
        self.assertEqual(got, [
            {"text": "the big sleep", "cursor": 13}, {"text": "a b c", "cursor": 5},
            {"text": "abcdef", "cursor": 6}, {"text": "Xc", "cursor": 1}, {"text": "z", "cursor": 1},
            {"text": "abc", "cursor": 1}, 300, 300])

    def test_keyboard_key(self):
        self.assertEqual(self.js("KodiInput.js", '[keyboardKey({type: "keyboard"}), keyboardKey(null)]'),
                         ["open", "ask"])

    def test_what_is_sent(self):
        got = self.js("KodiInput.js", """[
            dialogKey({type: "keyboard"}, "send", "the wire"), dialogKey({type: "keyboard"}, "send", ""),
            dialogKey({type: "keyboard"}, "cancel", "the wire"), dialogKey({type: "keyboard"}, "other", "x"),
            dialogKey(null, "send", "x"), dialogKey({type: "keyboard"}, "send", "y".repeat(400)).send.length]""")
        self.assertEqual(got, [
            {"open": False, "send": "the wire"}, {"open": False, "send": ""},
            {"open": False, "send": None}, {"open": True, "send": None},
            {"open": False, "send": None}, 300])


if __name__ == "__main__":
    unittest.main()


@unittest.skipUnless(shutil.which("node"), "node is needed to run TopBar.js")
class TopBarTest(EvalJs, unittest.TestCase):
    """The top bar's status words and the ☰ menu (ticket 043)."""

    def status(self, **s):
        return self.js("TopBar.js", "status(" + json.dumps(s) + ")")

    def test_status_words(self):
        def word(**s):
            got = self.status(**s)
            return got["word"], got["note"], got["why"], got["fix"]
        self.assertEqual(self.js("TopBar.js", "status(null)"),
                         {"word": "", "note": "", "why": "", "detail": "", "fix": False})
        self.assertEqual(word(ready=False), ("connecting", "", "", False))
        self.assertEqual(word(ready=True, reachable=True, error=""), ("connected", "", "", False))
        self.assertEqual(word(ready=True, connecting=True, reachable=False, error=""), ("connecting", "", "", False))
        self.assertEqual(word(ready=True, reachable=False, error="can't reach Kodi at kodi.example.lan:8080"),
                         ("offline", "", "can't reach Kodi at kodi.example.lan:8080", True))
        self.assertEqual(word(ready=True, reachable=False, error="", power={"state": "off"}), ("offline", "off", "", False))
        self.assertEqual(word(ready=True, reachable=False, error="", power={"state": "restarting"}),
                         ("offline", "restarting", "", False))
        # Kodi answers but refuses: its error says the fix.
        self.assertEqual(word(ready=True, reachable=True, error="wrong username or password"),
                         ("offline", "", "wrong username or password", False))
        self.assertEqual(word(ready=True, reachable=False, daemonError="omakodi daemon keeps stopping"),
                         ("offline", "", "omakodi daemon keeps stopping", False))
        # The daemon's trouble wins over a switch in progress.
        self.assertEqual(word(ready=True, connecting=True, daemonError="omakodi daemon keeps stopping")[0], "offline")

    def test_the_fix_goes_under_the_message(self):
        # The state's error: the phone remote's words, then the fix (ticket 053).
        got = self.status(ready=True, reachable=True,
                          error="Wrong username or password for Living room\nKodi refused the login; check "
                                "username and password in ~/.config/omakodi/config.json")
        self.assertEqual(got, {"word": "offline", "note": "", "why": "Wrong username or password for Living room",
                               "detail": "Kodi refused the login; check username and password in "
                                         "~/.config/omakodi/config.json", "fix": False})
        got = self.status(ready=True, reachable=False,
                          error="Can't reach Living room\nno answer from kodi.example.lan:8080 (away from home?)")
        self.assertEqual((got["why"], got["detail"], got["fix"]),
                         ("Can't reach Living room", "no answer from kodi.example.lan:8080 (away from home?)", True))
        got = self.status(ready=True, reachable=True, error="Living room answered HTTP 500")
        self.assertEqual((got["why"], got["detail"]), ("Living room answered HTTP 500", ""))

    def test_title_is_the_box_in_use(self):
        boxes = {"current": "bedroom.example.lan", "list": [
            {"name": "Living room", "host": "kodi.example.lan"}, {"name": "", "host": "bedroom.example.lan"}]}
        self.assertEqual(self.js("TopBar.js", "[title(%s), title(%s), title(null), title({current: '', list: []})]" % (
            json.dumps(boxes), json.dumps({**boxes, "current": "kodi.example.lan"}))),
                         ["bedroom.example.lan", "Living room", "", ""])

    def test_menu_rows_and_moves(self):
        boxes = {"current": "bedroom.example.lan", "list": [
            {"name": "Living room", "host": "kodi.example.lan"}, {"name": "Bedroom", "host": "bedroom.example.lan"}]}
        rows = self.js("TopBar.js", "menuRows(%s)" % json.dumps(boxes))
        self.assertEqual(rows, [{"kind": "box", "host": "kodi.example.lan"}, {"kind": "box", "host": "bedroom.example.lan"},
                                {"kind": "manage", "host": ""}, {"kind": "settings", "host": ""}])
        self.assertEqual(self.js("TopBar.js", "menuRows(null)"),
                         [{"kind": "manage", "host": ""}, {"kind": "settings", "host": ""}])
        self.assertEqual(self.js("TopBar.js", "[menuStart(menuRows(%s), 'bedroom.example.lan'),"
                                 " menuStart(menuRows(null), 'kodi.example.lan')]" % json.dumps(boxes)), [1, 0])
        self.assertEqual(self.js("TopBar.js", "[menuMove(0, -1, 4), menuMove(3, 1, 4), menuMove(1, 1, 4),"
                                 " menuMove(5, 0, 2), menuMove(0, 1, 0)]"), [0, 3, 2, 1, 0])


@unittest.skipUnless(shutil.which("node"), "node is needed to run the JS files")
class NowPlayingTest(EvalJs, unittest.TestCase):
    """The now-playing page's time row, play/pause, keys and Queue dialog (ticket 045)."""

    def test_clock(self):
        self.assertEqual(self.js("Format.js", "[clock(75.4, 600), clock(312, 6440), clock(3725, 6440),"
                                 " clock(6440, 6440), clock(-3, 0), clock(3725, 0)]"),
                         ["1:15", "0:05:12", "1:02:05", "1:47:20", "0:00", "1:02:05"])

    def test_speed_line(self):
        expr = """[{paused: false, speed: 1}, {paused: true, speed: 0}, {paused: false, speed: 0},
                   {paused: false, speed: 2}, {paused: false, speed: -4}, null]
          .map(function(p) { return speedLine(p, "Paused", "Speed: %1x") })"""
        self.assertEqual(self.js("Format.js", expr), ["", "Paused", "Paused", "Speed: 2x", "Speed: -4x", ""])

    def test_end_line(self):
        # 2026-11-18 21:00:00 UTC, 40:00 of 47:20 left at normal speed
        now = "Date.UTC(2026, 10, 18, 21, 0)"
        self.assertEqual(self.js("Format.js", "[endLine(440, 2840, %s, '%%1 · ends %%2'),"
                                 " endLine(440, 0, %s, '%%1 · ends %%2'),"
                                 " endLine(0, 6440, %s, '%%1 · ends %%2')]" % (now, now, now)),
                         ["47:20 · ends 21:40", "", "1:47:20 · ends 22:47"])

    def test_shows_pause(self):
        expr = """[{paused: false, speed: 1}, {paused: true, speed: 0}, {paused: false, speed: 2},
                   {paused: false, speed: -2}, null].map(showsPause)"""
        self.assertEqual(self.js("NowPlaying.js", expr), [True, False, False, False, False])

    def test_queue_status(self):
        q = {"position": 1, "start": 0, "total": 2, "items": [{"title": "A", "subtitle": ""}, {"title": "B", "subtitle": ""}]}
        self.assertEqual(self.js("NowPlaying.js", "[queueStatus(%s, true), queueStatus(%s, false), queueStatus(null, false),"
                                 " queueStatus({position: 0, start: 0, total: 3, items: []}, false), queueStatus(null, true)]"
                                 % (json.dumps(q), json.dumps(q))),
                         ["loading", "ready", "empty", "empty", "loading"])

    def test_queue_rows(self):
        q = {"position": 21, "start": 20, "total": 40, "items": [
            {"title": "The Lighthouse Keeper", "subtitle": "S01E03"},
            {"title": "Fog Over Harbour Street", "subtitle": ""},
            {"title": "", "subtitle": "Channel Nine"}]}
        self.assertEqual(self.js("NowPlaying.js", "queueRows(%s)" % json.dumps(q)), [
            {"position": 20, "label": "21. The Lighthouse Keeper", "detail": "S01E03", "playing": False, "removable": True},
            {"position": 21, "label": "22. Fog Over Harbour Street", "detail": "", "playing": True, "removable": False},
            {"position": 22, "label": "23. ?", "detail": "Channel Nine", "playing": False, "removable": True}])
        self.assertEqual(self.js("NowPlaying.js", "[queueRows(null), queueRows({position: 0, start: 0, items: []})]"), [[], []])

    def test_audio_track_words_like_the_phone_remote(self):
        # Ticket 051: language · Kodi's name; codec and channels only without a name;
        # a part once; "Audio N" (its place from 1) with nothing known.
        tracks = [
            {"index": 0, "name": "Director's commentary", "language": "English", "codec": "AC3", "channels": "stereo"},
            {"index": 1, "name": "", "language": "Norwegian", "codec": "EAC3", "channels": "5.1"},
            {"index": 3, "name": "", "language": "", "codec": "", "channels": ""},
            {"index": 4, "name": "VFF - DD+ 5.1", "language": "French", "codec": "EAC3", "channels": "5.1"},
            {"index": 5, "name": "English", "language": "English", "codec": "TRUEHD", "channels": "7.1"},
            {"index": 6, "name": "", "language": "", "codec": "DTS", "channels": ""},
            {"index": 7, "name": "", "language": "", "codec": "", "channels": "mono"},
            {"index": 8}]
        got = self.js("NowPlaying.js", "audioRows(%s, 'Audio %%1')" % json.dumps({"current": 1, "tracks": tracks}))
        self.assertEqual([r["label"] for r in got], [
            "English · Director's commentary", "Norwegian · EAC3 5.1", "Audio 3", "French · VFF - DD+ 5.1",
            "English", "DTS", "mono", "Audio 8"])
        self.assertEqual([r["current"] for r in got], [False, True] + [False] * 6)
        self.assertEqual([r["index"] for r in got], [0, 1, 3, 4, 5, 6, 7, 8])
        self.assertEqual(self.js("NowPlaying.js", "[audioRows(null, 'x'), audioRows({current: -1, tracks: [{index: 0}]},"
                                                  " 'Audio %1'), trackLabel(null, 0, ''), trackLabel({}, 4)]"),
                         [[], [{"index": 0, "label": "Audio 1", "current": False}], "Audio 1", "Audio 5"])

    def test_audio_words_from_the_daemon_to_the_list(self):
        # What the daemon reads from Kodi, as the list shows it: tags removed, the playing one marked.
        props = {"audiostreams": [
            {"index": 0, "name": "[B]Commentary[/B]", "language": "eng", "codec": "ac3", "channels": 2},
            {"index": 1, "name": "", "language": "nor", "codec": "eac3", "channels": 6},
            {"index": 2, "name": "", "language": "und", "codec": "", "channels": 0}],
            "currentaudiostream": {"index": 1}}
        got = self.js("NowPlaying.js", "audioRows(%s, 'Audio %%1')" % json.dumps(tracks(props)))
        self.assertEqual(got, [{"index": 0, "label": "English · Commentary", "current": False},
                               {"index": 1, "label": "Norwegian · EAC3 5.1", "current": True},
                               {"index": 2, "label": "Audio 3", "current": False}])

    def test_page_keys(self):
        # What the remote's keys do on the page: its buttons, the volume, Esc and n
        # close it, d u (D does nothing since 046); the D-pad, Enter, stop and the rest don't reach Kodi there.
        keys = [("0x01000000", ""), ("0", "n"), ("0", "d"), ("0", "D"), ("0", "u"), ("0x20", " "), ("0", "<"),
                ("0", ">"), ("0", "."), ("0", ","), ("0", "+"), ("0", "-"), ("0", "m"),
                ("0x01000013", ""), ("0x01000004", ""), ("0", "x"), ("0", "a"), ("0", "S"), ("0", "1")]
        expr = "[" + ", ".join('pageKey(lookup(%s, "%s", 0))' % k for k in keys) + "]"
        src = ""
        for name in ("RemoteKeys.js", "NowPlaying.js"):
            with open(os.path.join(ROOT, name), encoding="utf-8") as f:
                src += f.read() + "\n"
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
            f.write(src.replace(".pragma library\n", "\n"))
        try:
            got = self.js(f.name, expr)
        finally:
            os.unlink(f.name)
        self.assertEqual(got, [
            {"close": True}, {"nowPlaying": True}, {"details": True}, None, {"queueList": True},
            {"control": "playpause"}, {"control": "rewind"}, {"control": "fastforward"}, {"control": "next"},
            {"control": "previous"}, {"control": "volup"}, {"control": "voldown"}, {"control": "mute"},
            None, None, None, None, None, None])


@unittest.skipUnless(shutil.which("node"), "node is needed to run Toast.js")
class ToastTest(EvalJs, unittest.TestCase):
    """The remote's short message (ticket 048): a few seconds, an error until the next action."""

    def test_how_long(self):
        self.assertEqual(self.js("Toast.js", "[lasts(false), lasts(true), lasts(undefined), SHOW_MS]"),
                         [3000, 0, 3000, 3000])

    def test_what_a_result_shows(self):
        rows = [
            {"cmd": "play", "ok": True, "text": "Playing on Living room…"},
            {"cmd": "control", "ok": False, "text": "Can't reach Living room"},
            {"cmd": "control", "ok": True, "text": ""},
            {"cmd": "boxTest", "ok": True, "text": "✓ Kodi 21.3"},
            {"cmd": "browse", "ok": False, "text": "not reachable: …"},
            {"cmd": "discover", "ok": True, "text": "2 found"},
            {"cmd": "boxSave", "ok": False, "text": "can't save: a box with that address exists"},
        ]
        got = self.js("Toast.js", "%s.map(function(r) { return fromResult(r, false) })" % json.dumps(rows))
        self.assertEqual(got, [{"text": "Playing on Living room…", "error": False},
                               {"text": "Can't reach Living room", "error": True}, None, None, None, None,
                               {"text": "can't save: a box with that address exists", "error": True}])
        # The editor shows its own Save and Delete answers.
        self.assertIsNone(self.js("Toast.js", "fromResult(%s, true)" % json.dumps(rows[-1])))
        self.assertIsNone(self.js("Toast.js", "fromResult(null, false)"))

    def test_refusals_in_the_phones_words(self):
        # p / q and Send a link: text without a link (ticket 053).
        self.assertEqual(self.js("Toast.js", "[refusal('no link found'), refusal('text too long'), refusal(null)]"),
                         ["No link found", "text too long", ""])

    def test_the_remotes_own_notes(self):
        # An empty clipboard (p / q) and no audio streams (a), as the phone remote says them.
        with open(os.path.join(ROOT, "i18n", "en.json"), encoding="utf-8") as f:
            words = json.load(f)
        self.assertEqual(words["remote.clipboardEmpty"], "Nothing to send")
        self.assertEqual(words["remote.noAudioTrack"], "No audio streams to choose from")
