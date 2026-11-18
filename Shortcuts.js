.pragma library

// The shortcut strip's pure parts (SPEC "Shortcut buttons"), so they can be
// checked without the shell: the built-in icons, a typed path's check, and
// moving in the icon grid.

// name -> Material Design Icons code point in the Nerd Font. The names are
// lib/omakodi/shortcuts.py ICONS, in the same order (a test checks).
var ICONS = [
  ["movie", 0xF0381], ["film", 0xF0230], ["reel", 0xF07DE], ["clapper", 0xF0FCE],
  ["tv", 0xF0502], ["tv_classic", 0xF07F4], ["live_tv", 0xF0ECF], ["video", 0xF0BDC],
  ["play", 0xF040D], ["play_box", 0xF040B], ["subscriptions", 0xF0D40], ["camcorder", 0xF0A1C],
  ["headphones", 0xF02CB], ["music", 0xF075A], ["music_note", 0xF0387], ["music_video", 0xF0385],
  ["queue_music", 0xF0CB8], ["radio", 0xF0439], ["podcast", 0xF0994], ["microphone", 0xF036C],
  ["piano", 0xF067D], ["guitar", 0xF0771],
  ["pictures", 0xF02F9], ["image", 0xF02E9], ["camera", 0xF0100], ["picture_folder", 0xF024F],
  ["playlist", 0xF0411], ["star", 0xF04D2], ["heart", 0xF02D5], ["bookmark", 0xF00C3],
  ["thumb_up", 0xF0514], ["clock", 0xF0150], ["history", 0xF02DA], ["fire", 0xF0238],
  ["trending", 0xF0535], ["new", 0xF0394], ["explore", 0xF018C], ["search", 0xF0349],
  ["kids", 0xF0E7D], ["smile", 0xF01F2], ["drama", 0xF0D02], ["soccer", 0xF04B8],
  ["basketball", 0xF0806], ["racing", 0xF0D93], ["games", 0xF0EB7], ["fitness", 0xF01E6],
  ["news", 0xF1004], ["world", 0xF01E7], ["language", 0xF05CA], ["science", 0xF0096],
  ["school", 0xF1180], ["book", 0xF15D6], ["books", 0xF125F], ["nature", 0xF0405],
  ["pets", 0xF03E9], ["food", 0xF0A70], ["travel", 0xF001D], ["cars", 0xF010B],
  ["weather", 0xF0599], ["ideas", 0xF0336],
  ["home", 0xF02DC], ["folder", 0xF0256], ["drive", 0xF02CA], ["server", 0xF048B],
  ["cloud", 0xF0163], ["cloud_download", 0xF0B7D], ["download", 0xF01DA], ["addon", 0xF0A66],
  ["apps", 0xF003B], ["settings", 0xF08BB], ["info", 0xF02FD], ["link", 0xF0C94]
]

var BY_NAME = {}
for (var i = 0; i < ICONS.length; i++) BY_NAME[ICONS[i][0]] = ICONS[i][1]

function names() {
  return ICONS.map(function(pair) { return pair[0] })
}

// The glyph for an icon name; the folder for a name this version doesn't know.
function glyph(name) {
  return String.fromCodePoint(BY_NAME[name] !== undefined ? BY_NAME[name] : BY_NAME["folder"])
}

// The glyph a button shows when it has no Kodi art: its chosen icon, else the
// one matching what it opens.
function buttonGlyph(button) {
  if (!button) return glyph("folder")
  return glyph(button.icon || button.auto)
}

// A typed Kodi path or add-on id as the daemon keeps it, or "" when it is
// neither: the same as normalize() in lib/omakodi/shortcuts.py (a test runs
// both over the same texts).
var MAX_PATH = 2048
var ADDON_ID = /^[A-Za-z0-9_]+(?:\.[A-Za-z0-9_-]+)+$/
var BARE_PLUGIN = /^plugin:\/\/[^\/?#]+$/i
var CONTROL = /[\x00-\x1f\x7f-\x9f]/

function trimPython(s) {
  // Python's str.strip(): its whitespace, not JS's (no \ufeff, has \x1c-\x1f, \x85)
  return s.replace(/^[\t\n\v\f\r \x1c-\x1f\x85\xa0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]+/, "")
    .replace(/[\t\n\v\f\r \x1c-\x1f\x85\xa0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]+$/, "")
}

function codePoints(s) {
  var n = 0
  for (var i = 0; i < s.length; i++) {
    var c = s.charCodeAt(i)
    if (c < 0xdc00 || c > 0xdfff || i === 0 || s.charCodeAt(i - 1) < 0xd800 || s.charCodeAt(i - 1) > 0xdbff) n++
  }
  return n
}

function normalize(text) {
  var t = trimPython(String(text === undefined || text === null ? "" : text))
  if (t === "" || codePoints(t) > MAX_PATH || CONTROL.test(t)) return ""
  if (t.indexOf("://") >= 0) return BARE_PLUGIN.test(t) ? t + "/" : t
  if (ADDON_ID.test(t)) return t.toLowerCase().indexOf("plugin.") === 0 ? "plugin://" + t + "/" : t
  return ""
}

// Moving in the icon page: place 0 is the "Kodi's icon" tile on its own row,
// then the `icons` built-in icons in rows of `columns`. Returns the place
// after an arrow `dx`/`dy`; up from the first row, or left from the first
// icon, is Kodi's tile.
function iconMove(at, dx, dy, columns, icons) {
  if (at <= 0) return (dx > 0 || dy > 0) && icons > 0 ? 1 : 0
  var i = at - 1
  var next = i + dx + dy * columns
  if (next < 0) return dy < 0 || i === 0 ? 0 : at
  if (next >= icons) return at
  return next + 1
}
