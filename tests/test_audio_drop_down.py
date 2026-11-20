"""The audio track list as a drop-down under its key, like the phone remote
(ticket 063): where it opens (NowPlaying.dropDownPlace / dropDownWidth),
and its keys and closing, on the code the remote runs: the Panel.qml
functions and its key handler's audio block, cut out and run under node
against stubs. How it looks and takes clicks in a real Qt is in
test_audio_drop_down_qml.py.
"""

import json
import os
import re
import shutil
import subprocess
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

EVAL_RUNNER = r"""
const fs = require("fs"), vm = require("vm")
const src = fs.readFileSync(process.argv[1], "utf8").replace(/^\.pragma library\s*$/m, "")
const ctx = {}
vm.runInNewContext(src, ctx)
process.stdout.write(JSON.stringify(vm.runInContext(process.argv[2], ctx)))
"""

# Loads NowPlaying.js and RemoteKeys.js and the Panel functions (argv[2]) into
# one context with stubs; the key handler's audio block (argv[3]) becomes
# keyPress(event), which says "passed" when it leaves the key to the rest.
# Runs the steps (argv[5]) from the state (argv[4]) and prints what happened.
RUNNER = r"""
const fs = require("fs"), vm = require("vm")
const root = process.argv[1], fns = JSON.parse(process.argv[2]), block = process.argv[3]
const state = JSON.parse(process.argv[4]), steps = JSON.parse(process.argv[5])
const lib = n => { const c = {}; vm.runInNewContext(fs.readFileSync(root + "/" + n, "utf8").replace(/^\.pragma library\s*$/m, ""), c); return c }
const log = { said: [], sent: [], scrolled: [], powerClosed: 0, passed: 0 }
const words = JSON.parse(fs.readFileSync(root + "/i18n/en.json", "utf8"))
const ctx = {
  NowPlaying: lib("NowPlaying.js"), RemoteKeys: lib("RemoteKeys.js"),
  strings: { t: k => words[k] },
  Qt: { callLater: f => f(), Key_Up: 1, Key_Down: 2, Key_Return: 3, Key_Enter: 4, Key_Escape: 5, Key_A: 6,
        ControlModifier: 8, AltModifier: 16, MetaModifier: 32 },
  service: { setAudioTrack: i => { log.sent.push(["audio", i]); return "" } },
  say: (t, e) => log.said.push([t, e === true]),
  hush: () => {}, refusedOffline: () => false,
  closePowerMenu: () => { log.powerClosed++ },
  audioDropDown: { centre: at => log.scrolled.push(["centre", at]), reveal: at => log.scrolled.push(["reveal", at]) },
  connected: true, reachable: true, playing: null, audio: null,
  audioOpen: false, audioSelected: -1,
}
Object.assign(ctx, state)
ctx.root = ctx
vm.createContext(ctx)
for (const f of fns) vm.runInContext(f, ctx)
// The binding in Panel.qml: where the playing track is in the list.
Object.defineProperty(ctx, "audioAt", { get: () => {
  if (!ctx.audio) return -1
  for (let i = 0; i < ctx.audio.tracks.length; i++) if (ctx.audio.tracks[i].index === ctx.audio.current) return i
  return -1 } })
vm.runInContext("function keyPress(event) {\n" + block + "\nreturn 'passed'\n}", ctx)
for (const s of steps) {
  if (s.key) {
    const event = { key: ctx.Qt[s.key], modifiers: 0, isAutoRepeat: false, accepted: false }
    if (vm.runInContext("keyPress", ctx)(event) === "passed") log.passed++
  }
  else vm.runInContext(s.run, ctx)
}
log.audioOpen = ctx.audioOpen
log.audioSelected = ctx.audioSelected
process.stdout.write(JSON.stringify(log))
"""

PLAYING = {"title": "The Lighthouse Keeper", "kind": "video"}
THREE = {"current": 2, "tracks": [{"index": 0, "name": "Commentary", "language": "English"},
                                  {"index": 2, "name": "", "language": "Norwegian", "codec": "EAC3",
                                   "channels": "5.1"},
                                  {"index": 3}]}
ONE = {"current": 0, "tracks": [{"index": 0, "language": "English", "codec": "AAC", "channels": "stereo"}]}


def panel():
    with open(os.path.join(ROOT, "Panel.qml"), encoding="utf-8") as f:
        return f.read()


def function(source, name):
    start = source.index("  function %s(" % name)
    return source[start:source.index("\n  }\n", start) + 4]


def audio_block(source):
    """The key handler's part for the open list, as Panel.qml has it."""
    start = source.index("          if (root.audioOpen && !(event.modifiers")
    return source[start:source.index("          var hit = RemoteKeys.lookup(", start)]


@unittest.skipUnless(shutil.which("node"), "node is needed to run the JS files")
class AudioDropDownTest(unittest.TestCase):
    def js(self, expr):
        r = subprocess.run(["node", "-e", EVAL_RUNNER, os.path.join(ROOT, "NowPlaying.js"), expr],
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def run_remote(self, state, steps):
        source = panel()
        fns = [function(source, f) for f in ("toggleAudioList", "moveAudioSelection", "pickAudioTrack")]
        r = subprocess.run(["node", "-e", RUNNER, ROOT, json.dumps(fns), audio_block(source),
                            json.dumps(state), json.dumps(steps)],
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    # ---- where it opens ----------------------------------------------------------------

    def place(self, key, size, area, gap=4):
        return self.js("dropDownPlace(%s, %s, %s, %s)" % (json.dumps(key), json.dumps(size), json.dumps(area), gap))

    def test_under_the_key_its_left_edge_on_the_keys(self):
        area = {"x": 16, "y": 16, "width": 300, "height": 600}
        key = {"x": 16, "y": 300, "width": 56, "height": 40}
        self.assertEqual(self.place(key, {"width": 180, "height": 120}, area), {"x": 16, "y": 344})
        # Over the keys below it: it reaches past the key's own width.
        self.assertEqual(self.place(key, {"width": 300, "height": 168}, area), {"x": 16, "y": 344})

    def test_kept_inside_the_remote(self):
        area = {"x": 16, "y": 16, "width": 300, "height": 600}
        right = {"x": 260, "y": 300, "width": 56, "height": 40}
        self.assertEqual(self.place(right, {"width": 180, "height": 120}, area), {"x": 136, "y": 344})
        self.assertEqual(self.place(right, {"width": 400, "height": 120}, area)["x"], 16)

    def test_without_room_under_the_key_over_it(self):
        area = {"x": 16, "y": 16, "width": 300, "height": 600}
        low = {"x": 16, "y": 520, "width": 56, "height": 40}
        self.assertEqual(self.place(low, {"width": 180, "height": 120}, area), {"x": 16, "y": 396})
        # Room neither way: as high as it must, never above the remote.
        mid = {"x": 16, "y": 100, "width": 56, "height": 40}
        self.assertEqual(self.place(mid, {"width": 180, "height": 560}, area), {"x": 16, "y": 56})
        self.assertEqual(self.place(mid, {"width": 180, "height": 900}, area), {"x": 16, "y": 16})

    def test_bad_numbers_dont_break_it(self):
        self.assertEqual(self.js("dropDownPlace(null, null, null, null)"), {"x": 0, "y": 0})

    def test_as_wide_as_its_widest_row(self):
        self.assertEqual(self.js("[dropDownWidth(150.2, 24, 112, 300), dropDownWidth(20, 24, 112, 300),"
                                 " dropDownWidth(900, 24, 112, 300), dropDownWidth(NaN, 24, 112, 300),"
                                 " dropDownWidth(50, 0, 400, 300)]"),
                         [175, 112, 300, 112, 300])

    def test_in_the_remote_from_the_audio_key(self):
        source = panel()
        start = source.index("        AudioDropDown {")
        use = source[start:source.index("\n        }\n", start)]
        self.assertIn("key: Qt.rect(content.x + actionRow.x + audioKey.x, content.y + actionRow.y + audioKey.y,", use)
        self.assertIn("area: Qt.rect(card.padding, card.padding, width - card.padding * 2, height - card.padding * 2)",
                      use)
        self.assertIn("open: root.audioOpen && root.audio !== null", use)
        self.assertIn("onDismissed: root.audioOpen = false", use)
        self.assertIn("onPicked: function(at) { root.audioSelected = at; root.pickAudioTrack(at) }", use)
        # Over the power menu's layer (20, 21), under the ☰ menu (30).
        self.assertEqual(int(re.search(r"\n          z: (\d+)", use).group(1)), 22)
        # The audio key is the action row's first key.
        row = source[source.index("            id: actionRow"):]
        self.assertLess(row.index("id: audioKey"), row.index("Repeater {"))
        # No longer a list in the remote's column under now playing.
        column = source[source.index("          id: content\n"):source.index("        // ---- the power menu")]
        self.assertNotIn("ListView", column)
        self.assertNotIn("audioOpen", column.replace("selected: root.audioOpen", ""))

    # ---- keys and closing ------------------------------------------------------------

    def test_a_opens_it_on_the_playing_track(self):
        log = self.run_remote({"playing": PLAYING, "audio": THREE}, [{"run": "toggleAudioList()"}])
        self.assertTrue(log["audioOpen"])
        self.assertEqual(log["audioSelected"], 1)
        self.assertEqual(log["scrolled"], [["centre", 1]])
        self.assertEqual(log["powerClosed"], 1)
        self.assertEqual(log["sent"], [])

    def test_up_down_choose_and_enter_plays(self):
        log = self.run_remote({"playing": PLAYING, "audio": THREE},
                              [{"run": "toggleAudioList()"}, {"key": "Key_Up"}, {"key": "Key_Up"},
                               {"key": "Key_Down"}, {"key": "Key_Down"}, {"key": "Key_Down"}, {"key": "Key_Up"}])
        self.assertTrue(log["audioOpen"])
        self.assertEqual(log["audioSelected"], 1)
        self.assertEqual(log["scrolled"][1:], [["reveal", 0], ["reveal", 0], ["reveal", 1], ["reveal", 2],
                                               ["reveal", 2], ["reveal", 1]])
        log = self.run_remote({"playing": PLAYING, "audio": THREE},
                              [{"run": "toggleAudioList()"}, {"key": "Key_Up"}, {"key": "Key_Return"}])
        self.assertFalse(log["audioOpen"])
        self.assertEqual(log["sent"], [["audio", 0]])
        self.assertEqual(log["passed"], 0)

    def test_enter_on_the_playing_one_only_closes_it(self):
        for audio in (THREE, ONE):
            log = self.run_remote({"playing": PLAYING, "audio": audio},
                                  [{"run": "toggleAudioList()"}, {"key": "Key_Enter"}])
            self.assertFalse(log["audioOpen"])
            self.assertEqual(log["sent"], [])

    def test_esc_and_a_close_it(self):
        log = self.run_remote({"playing": PLAYING, "audio": THREE},
                              [{"run": "toggleAudioList()"}, {"key": "Key_Escape"}])
        self.assertFalse(log["audioOpen"])
        self.assertEqual(log["passed"], 0)  # Esc closes the list, not the remote
        log = self.run_remote({"playing": PLAYING, "audio": THREE},
                              [{"run": "toggleAudioList()"}, {"key": "Key_A"}, {"run": "toggleAudioList()"}])
        self.assertEqual(log["passed"], 1)  # a goes on to the remote's keys: the audio key
        self.assertFalse(log["audioOpen"])
        r = subprocess.run(["node", "-e", EVAL_RUNNER, os.path.join(ROOT, "RemoteKeys.js"), "lookup(0, 'a', 0)"],
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(json.loads(r.stdout), {"audioList": True})

    def test_a_click_on_a_track_plays_it(self):
        log = self.run_remote({"playing": PLAYING, "audio": THREE},
                              [{"run": "toggleAudioList()"}, {"run": "audioSelected = 2; pickAudioTrack(2)"}])
        self.assertEqual(log["sent"], [["audio", 3]])
        self.assertFalse(log["audioOpen"])

    def test_the_other_keys_work_while_it_is_open(self):
        log = self.run_remote({"playing": PLAYING, "audio": THREE, "audioOpen": True, "audioSelected": 1},
                              [{"key": "Key_A"}])
        self.assertEqual(log["passed"], 1)
        self.assertTrue(log["audioOpen"])

    def test_closed_it_takes_no_keys(self):
        log = self.run_remote({"playing": PLAYING, "audio": THREE},
                              [{"key": "Key_Up"}, {"key": "Key_Return"}, {"key": "Key_Escape"}])
        self.assertEqual(log["passed"], 3)
        self.assertEqual(log["sent"], [])

    def test_058s_messages_unchanged(self):
        log = self.run_remote({"playing": None, "audio": None}, [{"run": "toggleAudioList()"}])
        self.assertEqual(log["said"], [["Nothing is playing", True]])
        self.assertFalse(log["audioOpen"])
        log = self.run_remote({"playing": PLAYING, "audio": None}, [{"run": "toggleAudioList()"}])
        self.assertEqual(log["said"], [["No audio streams to choose from", False]])
        self.assertFalse(log["audioOpen"])

    def test_on_the_now_playing_page_a_does_nothing(self):
        # As the phone's now-playing screen, which has no audio key.
        r = subprocess.run(["node", "-e", EVAL_RUNNER, os.path.join(ROOT, "NowPlaying.js"),
                            "pageKey({audioList: true})"], capture_output=True, text=True, timeout=60)
        self.assertEqual(json.loads(r.stdout), None)


if __name__ == "__main__":
    unittest.main()
