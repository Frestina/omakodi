"""The remote's mouse keys (Panel.qml RemoteKey, ticket 044) in a real Qt.

Runs the component from Panel.qml under qmltestrunner (offscreen) with a
stand-in for the host's Button, which, like it, takes clicks in a
MouseArea of its own: a held arrow sends at once, then repeats after 0.4 s
every 0.11 s; OK sends on release and, held 0.5 s, sends the context menu
instead; a right click on OK is the context menu too. Skipped where Qt's
test runner isn't installed.
"""

import os
import shutil
import subprocess
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNNER = shutil.which("qmltestrunner") or shutil.which("qmltestrunner6") or (
    "/usr/lib/qt6/bin/qmltestrunner" if os.access("/usr/lib/qt6/bin/qmltestrunner", os.X_OK) else None)

FAKE_BUTTON = """import QtQuick
Rectangle {
  id: button
  signal clicked()
  signal rightClicked()
  property string text: ""
  property string iconText: ""
  property string tooltipText: ""
  property color foreground: "white"
  property real iconSize: 10
  property real fontSize: 10
  property color background: "grey"
  MouseArea {
    anchors.fill: parent
    hoverEnabled: true
    acceptedButtons: Qt.LeftButton | Qt.RightButton
    onClicked: function(mouse) { if (mouse.button === Qt.RightButton) button.rightClicked(); else button.clicked() }
  }
}
"""

TEST = """import QtQuick
import QtTest
import "RemoteKeys.js" as RemoteKeys
Item {
  id: root
  width: 300; height: 300
  property bool opened: true
  property color keyFill: "grey"
  property var sent: []
  function send(action, isRepeat) { sent.push(action + (isRepeat ? "*" : "")) }
  Row {
    RemoteKey { id: up; width: 50; height: 50; action: "up" }
    RemoteKey { id: ok; width: 50; height: 50; action: "select" }
    RemoteKey { id: mute; width: 50; height: 50; action: "mute" }
    RemoteKey { id: louder; width: 50; height: 50; action: "volup" }
  }
%COMPONENT%
  TestCase {
    name: "RemoteKey"
    when: windowShown
    function init() { sent = [] }
    function test_a_click_on_an_arrow_sends_it_once() {
      mouseClick(up, 10, 10)
      compare(sent.join(","), "up")
    }
    function test_a_held_arrow_repeats_after_the_delay() {
      mousePress(up, 10, 10)
      compare(sent.join(","), "up")
      wait(330)
      compare(sent.length, 1)
      wait(450)
      mouseRelease(up, 10, 10)
      var n = sent.length
      verify(n >= 3 && n <= 6, "sent " + n)
      compare(sent[1], "up*")
      wait(300)
      compare(sent.length, n)
    }
    function test_a_held_volume_key_repeats() {
      mousePress(louder, 10, 10)
      wait(650)
      mouseRelease(louder, 10, 10)
      verify(sent.length >= 2, "sent " + sent.length)
      compare(sent[0], "volup")
      compare(sent[1], "volup*")
    }
    function test_moving_off_a_held_key_stops_it() {
      mousePress(up, 10, 10)
      mouseMove(up, 250, 250)
      wait(700)
      mouseRelease(up, 250, 250)
      compare(sent.join(","), "up")
    }
    function test_a_click_on_ok_selects() {
      mouseClick(ok, 10, 10)
      compare(sent.join(","), "select")
    }
    function test_holding_ok_opens_the_context_menu() {
      mousePress(ok, 10, 10)
      wait(700)
      mouseRelease(ok, 10, 10)
      compare(sent.join(","), "context")
    }
    function test_a_right_click_on_ok_opens_the_context_menu() {
      mouseClick(ok, 10, 10, Qt.RightButton)
      compare(sent.join(","), "context")
    }
    function test_mute_doesnt_repeat() {
      mousePress(mute, 10, 10)
      wait(700)
      mouseRelease(mute, 10, 10)
      compare(sent.join(","), "mute")
    }
  }
}
"""


@unittest.skipUnless(RUNNER, "Qt's qmltestrunner is needed to run the QML")
class RemoteKeyTest(unittest.TestCase):
    def test_remote_key(self):
        with open(os.path.join(ROOT, "Panel.qml"), encoding="utf-8") as f:
            panel = f.read()
        start = panel.index("  component RemoteKey: Item {")
        end = panel.index("\n  // ----", start + 1)
        component = panel[start:end].replace("    Button {\n      id: remoteKeyButton",
                                             "    FakeButton {\n      id: remoteKeyButton")
        self.assertIn("FakeButton {", component)
        with tempfile.TemporaryDirectory() as d:
            shutil.copy(os.path.join(ROOT, "RemoteKeys.js"), d)
            with open(os.path.join(d, "FakeButton.qml"), "w", encoding="utf-8") as f:
                f.write(FAKE_BUTTON)
            test = os.path.join(d, "tst_remote_key.qml")
            with open(test, "w", encoding="utf-8") as f:
                f.write(TEST.replace("%COMPONENT%", component))
            env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
            r = subprocess.run([RUNNER, "-input", test], capture_output=True, text=True, timeout=120, env=env, cwd=d)
        self.assertEqual(r.returncode, 0, r.stdout[-3000:] + r.stderr[-2000:])
        self.assertIn(" 0 failed", r.stdout)


if __name__ == "__main__":
    unittest.main()
