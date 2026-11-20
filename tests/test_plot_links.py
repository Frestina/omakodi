"""Links in the Details dialog's plot (PlotLinks.js and Panel.qml DetailsPlot,
ticket 049).

PlotLinks.js runs under node: the plot's http(s) links are found (several,
at the end of a line, with punctuation after them, none), the rest stays
text, no other scheme is a link, and the markup escapes everything but the
links it builds. DetailsPlot runs under qmltestrunner (offscreen): what it
shows is exactly the plot, a click on a link asks to open that link, Tab
marks the links in turn and Enter opens the marked one, and it never takes
the keyboard. Each part is skipped where node or Qt's test runner isn't
installed.
"""

import json
import os
import shutil
import subprocess
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNNER = shutil.which("qmltestrunner") or shutil.which("qmltestrunner6") or (
    "/usr/lib/qt6/bin/qmltestrunner" if os.access("/usr/lib/qt6/bin/qmltestrunner", os.X_OK) else None)

# Loads PlotLinks.js and prints the JSON of each expression in the JSON array
# on stdin; `arg` in an expression is the matching value of the array in argv.
EVAL = r"""
const fs = require("fs"), vm = require("vm")
const src = fs.readFileSync(process.argv[1], "utf8").replace(/^\.pragma library\s*$/m, "")
const ctx = {}
vm.runInNewContext(src, ctx)
const jobs = JSON.parse(fs.readFileSync(0, "utf8"))
process.stdout.write(JSON.stringify(jobs.map(j => { ctx.arg = j[1]; return vm.runInContext(j[0], ctx) })))
"""


@unittest.skipUnless(shutil.which("node"), "node is needed to run PlotLinks.js")
class PlotLinksTest(unittest.TestCase):
    def run_js(self, jobs):
        r = subprocess.run(["node", "-e", EVAL, os.path.join(ROOT, "PlotLinks.js")],
                           input=json.dumps(jobs), capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def links(self, *plots):
        return self.run_js([["links(parts(arg))", p] for p in plots])

    def parts(self, plot):
        return self.run_js([["parts(arg)", plot]])[0]

    def test_several_links(self):
        plot = ("Watch the trailer: https://www.example.com/trailer and the making of "
                "http://video.example.org/making?id=42&t=3 or HTTPS://EXAMPLE.NET/A")
        self.assertEqual(self.links(plot), [[
            "https://www.example.com/trailer",
            "http://video.example.org/making?id=42&t=3",
            "HTTPS://EXAMPLE.NET/A",
        ]])

    def test_a_link_at_the_end_of_a_line(self):
        plot = "Follow us\nhttps://social.example.com/@channel\nMore below\nhttps://example.org"
        self.assertEqual(self.links(plot), [["https://social.example.com/@channel", "https://example.org"]])
        parts = self.parts(plot)
        self.assertEqual(parts[1], {"text": "https://social.example.com/@channel",
                                    "url": "https://social.example.com/@channel"})
        self.assertEqual(parts[2], {"text": "\nMore below\n", "url": ""})

    def test_punctuation_after_a_link(self):
        got = self.links(
            "Read https://example.com/a.",
            "See https://example.com/b, then https://example.com/c; https://example.com/d!",
            "Is it https://example.com/e? Yes: https://example.com/f…",
            "(see https://example.com/g)",
            "The film https://en.example.org/wiki/Big_Sleep_(film) is old.",
            "[https://example.com/h] and {https://example.com/i}",
            "**https://example.com/j**",
            "Quoted \"https://example.com/k\" and 'https://example.com/l' and <https://example.com/m>",
        )
        self.assertEqual(got, [
            ["https://example.com/a"],
            ["https://example.com/b", "https://example.com/c", "https://example.com/d"],
            ["https://example.com/e", "https://example.com/f"],
            ["https://example.com/g"],
            ["https://en.example.org/wiki/Big_Sleep_(film)"],
            ["https://example.com/h", "https://example.com/i"],
            ["https://example.com/j"],
            ["https://example.com/k", "https://example.com/l", "https://example.com/m"],
        ])
        # What was trimmed is text again.
        self.assertEqual(self.parts("(see https://example.com/g).")[-1], {"text": ").", "url": ""})

    def test_no_links(self):
        self.assertEqual(self.links("", "Just a plot.", "http", "https://", "https://.", "https:///path",
                                    "https://user@", "www.example.com", "example.com/path"),
                         [[]] * 9)
        self.assertEqual(self.parts("Just a plot."), [{"text": "Just a plot.", "url": ""}])
        self.assertEqual(self.parts(""), [])
        self.assertEqual(self.run_js([["parts(arg)", None], ["parts(arg)", 7]]), [[], []])

    def test_only_http_and_https(self):
        self.assertEqual(self.links(
            "ftp://example.org/file", "mailto:someone@example.org", "file:///etc/passwd",
            "javascript:alert(1)", "httpx://example.org", "data:text/html,hi", "plugin://plugin.video.example/",
            "http\u017f://example.org", "smb://kodi.example.lan/share",
        ), [[]] * 9)
        checks = self.run_js([["isWebLink(arg)", u] for u in (
            "https://example.com", "http://example.com/x?y=1#z", "HTTP://EXAMPLE.COM",
            "ftp://example.com", "javascript:alert(1)", "https://", "https://exa mple.com",
            "https://example.com/\n", "https://example.com/\x00", "https://example.com/<b>",
            "https://" + "a" * 4089, "https://" + "a" * 4088, " https://example.com", 42,
        )])
        self.assertEqual(checks, [True, True, True, False, False, False, False,
                                  False, False, False, False, True, False, False])
        self.assertEqual(self.run_js([["openCommand(arg)", u] for u in (
            "https://example.com/a b", "https://example.com/a?b=$(id)&c=`id`", "file:///etc/passwd")]),
            [None, ["xdg-open", "https://example.com/a?b=$(id)&c=`id`"], None])

    def test_the_other_text_stays_plain(self):
        plot = ("<b>Bold?</b> &amp; <img src=\"https://example.com/x.png\"> <a href='javascript:x'>y</a>\n"
                "[B]tags[/B] https://example.com/a?b=1&c=<2>")
        markup, links = self.run_js([["markup(parts(arg), -1, '#112233', '#ffffff')", plot],
                                     ["links(parts(arg))", plot]])
        self.assertEqual(links, ["https://example.com/x.png", "https://example.com/a?b=1&c="])
        body = markup.removeprefix('<div style="white-space:pre-wrap;line-height:120%">').removesuffix("</div>")
        # The only tags are the links and the line break the remote builds.
        tags = [t for t in body.split("<")[1:]]
        self.assertEqual([t.split(">")[0].split(" ")[0] for t in tags], ["a", "/a", "br", "a", "/a"])
        self.assertIn("&lt;b&gt;Bold?&lt;/b&gt; &amp;amp; &lt;img src=&quot;", body)
        self.assertIn("&lt;a href=&#39;javascript:x&#39;&gt;y&lt;/a&gt;", body)
        self.assertIn('<a href="1" style="color:#112233;text-decoration:underline">'
                      'https://example.com/a?b=1&amp;c=</a>&lt;2&gt;', body)
        self.assertNotIn("javascript:x'", body)

    def test_markup_marks_the_focused_link_and_checks_colours(self):
        plot = "a https://example.com/1 b https://example.com/2"
        focused, bad = self.run_js([
            ["markup(parts(arg), 1, '#112233', '#ffffff')", plot],
            ["markup(parts(arg), -1, 'red;background:url(x)', '#fff')", plot],
        ])
        self.assertIn('<a href="0" style="color:#112233;text-decoration:underline">', focused)
        self.assertIn('<a href="1" style="color:#ffffff;background-color:#112233;text-decoration:underline">',
                      focused)
        self.assertNotIn("url(x)", bad)
        self.assertIn("color:#3584e4", bad)

    def test_styles(self):
        # Ticket 052: Kodi's bold, italics and colours, as the daemon's plotStyles say.
        plot = "Big title\nblue <x> & https://example.com/a and end"
        styles = [{"from": 0, "to": 10, "bold": True, "italic": False, "color": ""},
                  {"from": 10, "to": 19, "bold": False, "italic": False, "color": "#add8e6"},
                  {"from": 20, "to": 46, "bold": True, "italic": True, "color": "#ff5252"}]
        markup, pieces = self.run_js([["markup(parts(arg[0]), -1, '#112233', '#ffffff', arg[1])", [plot, styles]],
                                      ["pieces(parts(arg[0]), arg[1])", [plot, styles]]])
        self.assertEqual("".join(p["text"] for p in pieces), plot)
        self.assertEqual([(p["text"], p["link"], p["bold"], p["italic"], p["color"]) for p in pieces], [
            ("Big title\n", -1, True, False, ""),
            ("blue <x> ", -1, False, False, "#add8e6"),
            ("&", -1, False, False, ""),
            (" ", -1, True, True, "#ff5252"),
            ("https://example.com/a", 0, True, True, "#ff5252"),
            (" and", -1, True, True, "#ff5252"),
            (" end", -1, False, False, ""),
        ])
        body = markup.removeprefix('<div style="white-space:pre-wrap;line-height:120%">').removesuffix("</div>")
        self.assertEqual(body,
                         "<b>Big title<br></b>"
                         '<span style="color:#add8e6">blue &lt;x&gt; </span>'
                         "&amp;"
                         '<span style="color:#ff5252"><b><i> </i></b></span>'
                         '<a href="0" style="color:#112233;text-decoration:underline"><b><i>https://example.com/a'
                         "</i></b></a>"
                         '<span style="color:#ff5252"><b><i> and</i></b></span> end')

    def test_styles_cut_links_and_keep_their_number(self):
        plot = "a https://example.com/1 b https://example.com/2"
        styles = [{"from": 10, "to": 30, "bold": True, "italic": False, "color": ""}]
        pieces, focused = self.run_js([["pieces(parts(arg[0]), arg[1])", [plot, styles]],
                                       ["markup(parts(arg[0]), 1, '#112233', '#ffffff', arg[1])", [plot, styles]]])
        self.assertEqual("".join(p["text"] for p in pieces), plot)
        self.assertEqual([p["link"] for p in pieces], [-1, 0, 0, -1, 1, 1])
        self.assertEqual([p["bold"] for p in pieces], [False, False, True, True, True, False])
        self.assertEqual(focused.count('<a href="1" style="color:#ffffff;background-color:#112233;'), 2)
        self.assertEqual(focused.count('<a href="0" style="color:#112233;'), 2)

    def test_styles_never_bring_markup(self):
        plot = "one two three"
        bad = [None, "junk", {"from": 0, "to": 3, "color": "red;background:url(x)", "bold": "<script>"},
               {"from": 4, "to": 7, "color": 7}, {"from": 8, "to": 13, "color": "#12345", "italic": True}]
        got = self.run_js([["markup(parts(arg[0]), -1, '#112233', '#ffffff', arg[1])", [plot, bad]],
                           ["markup(parts(arg), -1, '#112233', '#ffffff', 'x')", plot],
                           ["markup(parts(arg), -1, '#112233', '#ffffff', [{from: 5, to: 2, bold: true}])", plot],
                           ["markup(parts(arg), -1, '#112233', '#ffffff')", plot]])
        body = got[0].removeprefix('<div style="white-space:pre-wrap;line-height:120%">').removesuffix("</div>")
        self.assertEqual(body, "one two <i>three</i>")
        self.assertEqual(len(set(got[1:])), 1)
        self.assertNotIn("<b>", got[1])

    # Ticket 056: Kodi's colours made readable on the dialog's background.
    def hue_sat(self, hex_colour):
        return self.run_js([["toHsl(arg)", hex_colour]])[0]

    def test_contrast_rule(self):
        got = self.run_js([["[contrast('#000000', '#ffffff'), contrast('#ffffff', '#ffffff'), "
                            "contrast('#ffffff', '#000000'), contrast('#767676', '#ffffff'), READABLE]", None]])[0]
        self.assertAlmostEqual(got[0], 21, places=3)
        self.assertAlmostEqual(got[1], 1, places=6)
        self.assertAlmostEqual(got[2], 21, places=3)
        self.assertAlmostEqual(got[3], 4.54, places=2)  # WCAG's well-known grey on white
        self.assertEqual(got[4], 4.5)

    def check_made_readable(self, cases, darker):
        jobs = []
        for colour, background in cases:
            jobs.append(["[readable(arg[0], arg[1]), contrast(arg[0], arg[1])]", [colour, background]])
        for (colour, background), (out, before) in zip(cases, self.run_js(jobs)):
            with self.subTest(colour=colour, background=background):
                self.assertLess(before, 4.5)
                self.assertRegex(out, r"^#[0-9a-f]{6}$")
                after, lum_in, lum_out = self.run_js([["[contrast(arg[0], arg[1]), luminance(arg[2]), "
                                                       "luminance(arg[0])]", [out, background, colour]]])[0]
                self.assertGreaterEqual(after, 4.5)
                self.assertLess(after, 4.8)  # just enough, not black or white
                if darker:
                    self.assertLess(lum_out, lum_in)
                else:
                    self.assertGreater(lum_out, lum_in)
                a, b = self.hue_sat(colour), self.hue_sat(out)
                if a["s"] > 0:
                    diff = abs(a["h"] - b["h"]) % 360
                    self.assertLess(min(diff, 360 - diff), 2)  # hue kept
                    self.assertAlmostEqual(a["s"], b["s"], delta=0.03)
                else:
                    self.assertEqual(b["s"], 0)

    def test_darker_on_a_light_theme(self):
        self.check_made_readable([("#add8e6", "#fafafa"), ("#00ffff", "#eff1f5"), ("#90ee90", "#ffffff"),
                                  ("#ffff00", "#ffffff"), ("#3ea6ff", "#fdf6e3"), ("#aaaaaa", "#ffffff")],
                                 darker=True)

    def test_lighter_on_a_dark_theme(self):
        self.check_made_readable([("#0000ff", "#1e1e2e"), ("#000000", "#000000"), ("#8b0000", "#282828"),
                                  ("#333333", "#1a1b26")], darker=False)

    def test_white_on_white(self):
        out = self.run_js([["readable('#ffffff', '#ffffff')", None]])[0]
        self.assertEqual(out, "#767676")

    def test_a_colour_that_reads_is_left_alone(self):
        got = self.run_js([["readable('#ff5252', '#1e1e2e')", None], ["readable('#add8e6', '#1a1b26')", None],
                           ["readable('#8b0000', '#ffffff')", None], ["readable('#FFFFFF', '#000000')", None],
                           ["readable('#ffffff', 'x')", None], ["readable('red', '#ffffff')", None]])
        self.assertEqual(got, ["#ff5252", "#add8e6", "#8b0000", "#FFFFFF", "#ffffff", "red"])

    def test_markup_draws_the_readable_colours(self):
        plot = "white text, blue text and https://example.com/a"
        styles = [{"from": 0, "to": 10, "color": "#ffffff"}, {"from": 12, "to": 21, "color": "#add8e6"},
                  {"from": 26, "to": 47, "color": "#ffffff"}]
        blue, light, dark, none, bad = self.run_js([
            ["readable('#add8e6', '#ffffff')", None],
            ["markup(parts(arg[0]), -1, '#112233', '#ffffff', arg[1], '#ffffff')", [plot, styles]],
            ["markup(parts(arg[0]), -1, '#112233', '#ffffff', arg[1], '#1e1e2e')", [plot, styles]],
            ["markup(parts(arg[0]), -1, '#112233', '#ffffff', arg[1])", [plot, styles]],
            ["markup(parts(arg[0]), -1, '#112233', '#ffffff', arg[1], 'red;x:url(y)')", [plot, styles]]])
        self.assertIn('<span style="color:#767676">white text</span>', light)
        self.assertNotEqual(blue, "#add8e6")
        self.assertIn('<span style="color:' + blue + '">blue text</span>', light)
        self.assertNotIn('color:#ffffff">', light)
        self.assertIn('<a href="0" style="color:#112233;', light)  # a link keeps the link colour
        self.assertIn('<span style="color:#ffffff">white text</span>', dark)
        self.assertIn('<span style="color:#add8e6">blue text</span>', dark)
        self.assertEqual(none, dark)
        self.assertEqual(bad, dark)
        self.assertNotIn("url(y)", bad)

    def test_helpers(self):
        plot = "x\nhttps://example.com/1 yy https://example.com/22"
        got = self.run_js([
            ["offset(parts(arg), 0)", plot], ["offset(parts(arg), 1)", plot], ["offset(parts(arg), 2)", plot],
            ["[step(0, -1, 1), step(3, -1, 1), step(3, -1, -1), step(3, 2, 1), step(3, 0, -1), step(3, 1, 1)]", None],
            ["[linkIndex('0', 2), linkIndex('1', 2), linkIndex('2', 2), linkIndex('-1', 2), "
             "linkIndex('https://example.com', 2), linkIndex('1x', 2)]", None],
            ["css({r: 1, g: 0.5, b: 0})", None], ["css(null)", None],
        ])
        self.assertEqual(got, [2, 27, -1, [-1, 0, 2, 0, 2, 2], [0, 1, -1, -1, -1, -1], "#ff8000", "#000000"])


class PlotBackgroundTest(unittest.TestCase):
    """Ticket 059: what the plot is drawn on (Panel.qml). The now-playing
    page covers the card's blurred art, and the Details dialog is an opaque
    rectangle in the card's colour, so the art never shows behind the plot:
    readable() against that one colour (056) is the whole check. Should the
    dialog ever let the art through, these fail, and the colours must then
    be checked against the popup colour blended with black and with white at
    the art's strength as well."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(ROOT, "Panel.qml"), encoding="utf-8") as f:
            cls.lines = f.read().split("\n")

    def blocks_around(self, needle):
        """The lines opening the blocks the first line with `needle` is in,
        outermost first."""
        stack = []
        for i, line in enumerate(self.lines):
            if needle in line:
                return list(stack)
            for ch in line.split("//")[0]:
                if ch == "{":
                    stack.append(i)
                elif ch == "}":
                    stack.pop()
        self.fail(needle + " not found")

    def own_lines(self, start):
        """The property lines of the block opening on line `start` (not
        those of the blocks inside it)."""
        depth, out = 0, []
        for line in self.lines[start:]:
            code = line.split("//")[0]
            if depth == 1 and code.strip():
                out.append(code.strip())
            depth += code.count("{") - code.count("}")
            if depth <= 0 and out:
                break
        return out

    def test_the_plot_is_drawn_on_the_card_colour_alone(self):
        ancestors = self.blocks_around("id: detailsPlot")
        plot = ancestors[-1]
        self.assertEqual(self.lines[plot].strip(), "DetailsPlot {")
        self.assertIn("backgroundColor: card.color", self.own_lines(plot))
        # The nearest rectangle under the plot: the dialog, opaque in the
        # card's colour, nothing between it and the plot made translucent.
        under = [at for at in ancestors if self.lines[at].strip() == "Rectangle {"][-1]
        dialog = self.own_lines(under)
        self.assertIn("color: card.color", dialog)
        for at in ancestors[ancestors.index(under):]:
            for line in self.own_lines(at):
                self.assertFalse(line.startswith(("opacity:", "layer.")), (self.lines[at].strip(), line))
        # The card's colour is the theme's popup colour made opaque.
        card = self.lines.index("    BorderSurface {")
        self.assertIn("color: Qt.rgba(themed.r, themed.g, themed.b, 1)", self.own_lines(card))


FAKE_COMMONS = {
    "qmldir": "module qs.Commons\nsingleton Color 1.0 Color.qml\nsingleton Style 1.0 Style.qml\n",
    "Color.qml": ("pragma Singleton\nimport QtQuick\nQtObject {\n"
                  "  property QtObject popups: QtObject { property color text: \"white\";"
                  " property color background: \"#1e1e2e\" }\n"
                  "  property color accent: \"#336699\"\n}\n"),
    "Style.qml": ("pragma Singleton\nimport QtQuick\nQtObject {\n"
                  "  property QtObject font: QtObject { property string family: \"\"; property real body: 14 }\n}\n"),
}

TEST = """import QtQuick
import QtTest
import qs.Commons
import qs.Commons as Commons
import "PlotLinks.js" as PlotLinks
Item {
  id: root
  width: 400; height: 600
  property var opened: []
  Item { id: keys; width: 10; height: 10; focus: true }
  DetailsPlot {
    id: plot
    y: 20
    width: 300
    linkColor: Commons.Color.accent
    focusedColor: "black"
    backgroundColor: Commons.Color.popups.background
    onOpenLink: function(url) { root.opened.push(url) }
  }
%COMPONENT%
  TestCase {
    name: "DetailsPlot"
    when: windowShown
    readonly property string sample: "Our <b>new</b> video & more.\\n\\nShop: https://shop.example.com/x?a=1&b=2.\\n"
      + "Chat (https://chat.example.org/room) or mailto:fan@example.com\\nhttps://example.net/end"
    function init() { opened = []; plot.plot = ""; keys.forceActiveFocus() }
    function shown() { return plot.getText(0, plot.length) }
    function linkPoint(i) {
      var r = plot.positionToRectangle(PlotLinks.offset(plot.parts, i) + 2)
      return Qt.point(r.x + 1, r.y + r.height / 2)
    }

    function test_shows_the_plot_as_it_is() {
      plot.plot = sample
      compare(shown(), sample.replace(/\\n/g, "\\u2028"))
      compare(plot.links, ["https://shop.example.com/x?a=1&b=2", "https://chat.example.org/room",
                           "https://example.net/end"])
    }
    function test_a_click_on_a_link_opens_it() {
      plot.plot = sample
      for (var i = 0; i < 3; i++) {
        var p = linkPoint(i)
        compare(plot.linkAt(p.x, p.y), String(i))
        mouseClick(plot, p.x, p.y)
      }
      compare(opened, plot.links)
      verify(keys.activeFocus)  // the remote keeps the keyboard
      verify(!plot.activeFocus)
    }
    function test_a_click_on_text_opens_nothing() {
      plot.plot = sample
      mouseClick(plot, 2, 2)
      compare(opened.length, 0)
    }
    function test_tab_marks_the_links_in_turn_and_enter_opens_it() {
      plot.plot = sample
      compare(plot.focusedLink, -1)
      verify(!plot.openFocused())
      var r = plot.moveFocus(1)
      compare(plot.focusedLink, 0)
      verify(r.height > 0)
      var r1 = plot.moveFocus(1)
      compare(plot.focusedLink, 1)
      verify(r1.y > r.y)
      plot.moveFocus(1)
      plot.moveFocus(1)  // round the end
      compare(plot.focusedLink, 0)
      plot.moveFocus(-1)
      compare(plot.focusedLink, 2)
      verify(plot.openFocused())
      compare(opened, ["https://example.net/end"])
      compare(shown(), sample.replace(/\\n/g, "\\u2028"))  // marking changes no text
    }
    function test_a_new_plot_marks_nothing() {
      plot.plot = sample
      plot.moveFocus(1)
      plot.plot = "Another plot, https://example.com"
      compare(plot.focusedLink, -1)
    }
    function test_styles_change_no_text_and_links_still_work() {
      plot.plot = sample
      plot.styles = [{from: 0, to: 12, bold: true, italic: false, color: ""},
                     {from: 12, to: 40, bold: false, italic: true, color: "#ff5252"},
                     {from: 40, to: 200, bold: true, italic: false, color: "#add8e6"}]
      compare(shown(), sample.replace(/\\n/g, "\\u2028"))
      // Qt keeps them in its own HTML: bold, italic and the colours drawn.
      verify(plot.text.indexOf("font-weight:700") >= 0)
      verify(plot.text.indexOf("font-style:italic") >= 0)
      verify(plot.text.indexOf("color:#ff5252") >= 0)
      verify(plot.text.indexOf("color:#add8e6") >= 0)
      for (var i = 0; i < 3; i++) {
        var p = linkPoint(i)
        compare(plot.linkAt(p.x, p.y), String(i))
        mouseClick(plot, p.x, p.y)
      }
      compare(opened, plot.links)
      plot.styles = []
    }
    function test_colours_follow_the_theme() {
      // Ticket 056: on a light theme Kodi's light colours are drawn darker,
      // on a dark one as Kodi gave them; a theme change while open redraws.
      plot.plot = sample
      plot.styles = [{from: 0, to: 12, bold: false, italic: false, color: "#ffffff"},
                     {from: 12, to: 40, bold: false, italic: false, color: "#add8e6"}]
      verify(plot.text.indexOf("color:#ffffff") >= 0)
      verify(plot.text.indexOf("color:#add8e6") >= 0)
      Commons.Color.popups.background = "#fafafa"
      verify(plot.text.indexOf("color:#ffffff") < 0)
      verify(plot.text.indexOf("color:#add8e6") < 0)
      verify(plot.text.indexOf("color:" + PlotLinks.readable("#ffffff", "#fafafa")) >= 0)
      verify(plot.text.indexOf("color:" + PlotLinks.readable("#add8e6", "#fafafa")) >= 0)
      compare(shown(), sample.replace(/\\n/g, "\\u2028"))
      Commons.Color.popups.background = "#1e1e2e"
      verify(plot.text.indexOf("color:#ffffff") >= 0)
      verify(plot.text.indexOf("color:#add8e6") >= 0)
      plot.styles = []
    }
    function test_without_links() {
      plot.plot = "No links here: www.example.com, ftp://example.com"
      compare(plot.links.length, 0)
      compare(plot.moveFocus(1), null)
      compare(plot.focusedLink, -1)
      verify(!plot.openFocused())
      mouseClick(plot, 5, 5)
      compare(opened.length, 0)
    }
    function test_keys_and_a_press_leave_the_keyboard_alone() {
      plot.plot = sample
      mouseClick(plot, 3, 3)
      verify(keys.activeFocus)
      verify(plot.readOnly)
    }
  }
}
"""


@unittest.skipUnless(RUNNER, "Qt's qmltestrunner is needed to run the QML")
class DetailsPlotTest(unittest.TestCase):
    def test_details_plot(self):
        with open(os.path.join(ROOT, "Panel.qml"), encoding="utf-8") as f:
            panel = f.read()
        start = panel.index("  component DetailsPlot: TextEdit {")
        end = panel.index("\n  // A heading in the Details dialog", start)
        component = panel[start:end]
        with tempfile.TemporaryDirectory() as d:
            shutil.copy(os.path.join(ROOT, "PlotLinks.js"), d)
            commons = os.path.join(d, "imports", "qs", "Commons")
            os.makedirs(commons)
            for name, text in FAKE_COMMONS.items():
                with open(os.path.join(commons, name), "w", encoding="utf-8") as f:
                    f.write(text)
            test = os.path.join(d, "tst_details_plot.qml")
            with open(test, "w", encoding="utf-8") as f:
                f.write(TEST.replace("%COMPONENT%", component))
            env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
            r = subprocess.run([RUNNER, "-import", os.path.join(d, "imports"), "-input", test],
                               capture_output=True, text=True, timeout=120, env=env, cwd=d)
        out = r.stdout[-4000:] + r.stderr[-3000:]
        self.assertEqual(r.returncode, 0, out)
        self.assertIn(" 0 failed", r.stdout)
        self.assertNotIn("ReferenceError", out)
        self.assertNotIn("TypeError", out)


if __name__ == "__main__":
    unittest.main()
