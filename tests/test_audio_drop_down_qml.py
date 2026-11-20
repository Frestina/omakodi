"""The audio track list as a drop-down under its key (Panel.qml
AudioDropDown, ticket 063) in a real Qt.

Runs the component from Panel.qml under qmltestrunner (offscreen): it opens
under the key with its left edge on the key's, over what is below, as a
phone remote's menu; one row for one track, five then it scrolls; as wide
as its widest row within the remote; the playing track in the accent colour
and bold, the selected row shaded; a click on a row picks it, a click beside
it (also on the key) only closes it. Skipped where Qt's test runner isn't
installed. The keys (Up/Down, Enter, Esc, a) are in test_audio_drop_down.py.
"""

import os
import shutil
import subprocess
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNNER = shutil.which("qmltestrunner") or shutil.which("qmltestrunner6") or (
    "/usr/lib/qt6/bin/qmltestrunner" if os.access("/usr/lib/qt6/bin/qmltestrunner", os.X_OK) else None)

TEST = """import QtQuick
import QtTest
import "NowPlaying.js" as NowPlaying
Item {
  id: root
  width: 320; height: 480
  property var picks: []
  property int dismissals: 0
  property int keyClicks: 0
  property int belowClicks: 0
  property var one: [{index: 0, label: "English · AAC stereo", current: true}]
  property var three: [{index: 0, label: "English · Commentary", current: false},
                       {index: 2, label: "Norwegian · EAC3 5.1", current: true},
                       {index: 3, label: "Audio 3", current: false}]
  property var eight: [0, 1, 2, 3, 4, 5, 6, 7].map(function(i) { return {index: i, label: "Audio " + (i + 1), current: i === 0} })
  property var long: [{index: 0, label: "Norwegian · The director and the writer talk all the way through it", current: true}]
  Rectangle {  // the audio key
    id: audioKey
    x: 16; y: 120; width: 56; height: 40
    MouseArea { anchors.fill: parent; onClicked: root.keyClicks++ }
  }
  Rectangle {  // the keys under it
    x: 0; y: 170; width: 320; height: 300
    MouseArea { anchors.fill: parent; onClicked: root.belowClicks++ }
  }
%COMPONENT%
  AudioDropDown {
    id: drop
    anchors.fill: parent
    key: Qt.rect(audioKey.x, audioKey.y, audioKey.width, audioKey.height)
    area: Qt.rect(16, 16, width - 32, height - 32)
    gap: 4; inset: 4; textInset: 8; least: 112; leastRowHeight: 30
    fill: "#202020"; textColor: "#eeeeee"; accent: "#ff8800"; fontSize: 14
    rows: root.three
    onPicked: function(at) { root.picks.push(at) }
    onDismissed: { root.dismissals++; drop.open = false }
  }
  TestCase {
    name: "AudioDropDown"
    when: windowShown
    function init() {
      root.picks = []; root.dismissals = 0; root.keyClicks = 0; root.belowClicks = 0
      audioKey.y = 120
      drop.rows = root.three
      drop.selected = 1
      drop.open = true
      wait(20)
    }
    function cleanup() { drop.open = false }
    function test_it_drops_down_from_the_key() {
      verify(drop.visible)
      compare(drop.listX, audioKey.x)
      compare(drop.listY, audioKey.y + audioKey.height + 4)
      verify(drop.listY > audioKey.y + audioKey.height, "under the key")
    }
    function test_it_is_hidden_until_opened() {
      drop.open = false
      verify(!drop.visible)
      drop.open = true
      verify(drop.visible)
    }
    function test_one_track_one_row() {
      drop.rows = root.one
      compare(drop.listHeight, drop.rowHeight + 8)
    }
    function test_three_tracks_three_rows() {
      compare(drop.listHeight, drop.rowHeight * 3 + 8)
    }
    function test_five_rows_then_it_scrolls() {
      drop.rows = root.eight
      compare(drop.listHeight, drop.rowHeight * 5 + 8)
    }
    function test_as_wide_as_its_rows_within_the_remote() {
      verify(drop.listWidth >= 112, "at least the least: " + drop.listWidth)
      verify(drop.listWidth < drop.area.width, "narrower than the remote: " + drop.listWidth)
      var narrow = drop.listWidth
      drop.rows = root.one
      drop.rows = root.long
      compare(drop.listWidth, drop.area.width)
      verify(drop.listX + drop.listWidth <= drop.area.x + drop.area.width)
      verify(drop.listWidth > narrow)
    }
    function test_measured_while_closed() {
      drop.open = false
      drop.rows = root.long
      drop.open = true
      compare(drop.listWidth, drop.area.width)
    }
    function test_the_playing_track_in_the_accent_and_bold() {
      var playing = findChild(drop, "audioRow1")
      var other = findChild(drop, "audioRow0")
      verify(playing !== null && other !== null)
      verify(playing.font.bold)
      verify(!other.font.bold)
      verify(Qt.colorEqual(playing.color, "#ff8800"))
      verify(Qt.colorEqual(other.color, "#eeeeee"))
      compare(playing.text, "Norwegian · EAC3 5.1")
    }
    function test_the_selected_row_is_shaded() {
      drop.selected = 2
      verify(findChild(drop, "audioShade2").opacity > 0)
      compare(findChild(drop, "audioShade1").opacity, 0)
    }
    function test_a_click_on_a_row_picks_it() {
      mouseClick(drop, drop.listX + 30, drop.listY + 4 + drop.rowHeight * 2.5)
      compare(root.picks.join(","), "2")
      compare(root.dismissals, 0)
      compare(root.belowClicks, 0)
    }
    function test_a_click_between_the_rows_stays_in_the_list() {
      mouseClick(drop, drop.listX + 30, drop.listY + 2)
      compare(root.picks.length, 0)
      compare(root.dismissals, 0)
      verify(drop.open)
    }
    function test_a_click_beside_it_only_closes_it() {
      mouseClick(drop, 300, 400)
      compare(root.dismissals, 1)
      compare(root.belowClicks, 0)
      compare(root.picks.length, 0)
      verify(!drop.visible)
    }
    function test_a_click_on_the_key_closes_it() {
      mouseClick(drop, audioKey.x + 10, audioKey.y + 10)
      compare(root.dismissals, 1)
      compare(root.keyClicks, 0)
    }
    function test_closed_it_takes_no_clicks() {
      drop.open = false
      mouseClick(root, 300, 400)
      compare(root.belowClicks, 1)
      compare(root.dismissals, 0)
    }
    function test_it_scrolls_to_the_chosen_row() {
      drop.rows = root.eight
      drop.centre(0)
      drop.reveal(7)
      wait(20)
      var row = findChild(drop, "audioRow7")
      verify(row !== null)
      var at = row.mapToItem(drop, 0, 0)
      verify(at.y >= drop.listY && at.y + row.height <= drop.listY + drop.listHeight, "row 8 at " + at.y)
    }
    function test_without_room_under_the_key_it_opens_over_it() {
      audioKey.y = 400
      compare(drop.listY, audioKey.y - 4 - drop.listHeight)
      compare(drop.listX, audioKey.x)
    }
  }
}
"""


@unittest.skipUnless(RUNNER, "Qt's qmltestrunner is needed to run the QML")
class AudioDropDownQmlTest(unittest.TestCase):
    def test_audio_drop_down(self):
        with open(os.path.join(ROOT, "Panel.qml"), encoding="utf-8") as f:
            panel = f.read()
        start = panel.index("  component AudioDropDown: Item {")
        end = panel.index("\n  // ----", start + 1)
        component = panel[start:end]
        with tempfile.TemporaryDirectory() as d:
            shutil.copy(os.path.join(ROOT, "NowPlaying.js"), d)
            test = os.path.join(d, "tst_audio_drop_down.qml")
            with open(test, "w", encoding="utf-8") as f:
                f.write(TEST.replace("%COMPONENT%", component))
            env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
            r = subprocess.run([RUNNER, "-input", test], capture_output=True, text=True, timeout=120, env=env, cwd=d)
        self.assertEqual(r.returncode, 0, r.stdout[-3000:] + r.stderr[-2000:])
        self.assertIn(" 0 failed", r.stdout)
        self.assertNotIn("Binding loop", r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
