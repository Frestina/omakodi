.pragma library

// The remote's key map (SPEC "Remote panel"). Pure, so it can be checked
// without the shell. `key` is Qt's key code after Util.readingKey (so Left
// and Right are already swapped for right-to-left languages).

var KEY_ESCAPE = 0x01000000
var KEY_BACKSPACE = 0x01000003
var KEY_RETURN = 0x01000004
var KEY_ENTER = 0x01000005
var KEY_LEFT = 0x01000012
var KEY_UP = 0x01000013
var KEY_RIGHT = 0x01000014
var KEY_DOWN = 0x01000015
var KEY_SPACE = 0x20

var CTRL = 0x04000000
var ALT = 0x08000000
var META = 0x10000000

var BY_KEY = {}
BY_KEY[KEY_UP] = "up"
BY_KEY[KEY_DOWN] = "down"
BY_KEY[KEY_LEFT] = "left"
BY_KEY[KEY_RIGHT] = "right"
BY_KEY[KEY_RETURN] = "select"
BY_KEY[KEY_ENTER] = "select"
BY_KEY[KEY_BACKSPACE] = "back"
BY_KEY[KEY_SPACE] = "playpause"

var BY_TEXT = {
  "+": "volup", "=": "volup", "-": "voldown", "m": "mute",
  "c": "context", "i": "info", "o": "osd", "h": "home", "x": "stop", "f": "fullscreen",
  ".": "next", ",": "previous",  // Kodi's own keys for them
  "<": "rewind", ">": "fastforward"  // one key on a Nordic keyboard, Shift for >
}

// Returns {close: true}, {control: "<action>"}, {link: "play"|"queue"},
// {queueList: true} (show or hide the queue), {details: true} (show or hide
// the details card), {wholePlot: true} or null.
function lookup(key, text, modifiers) {
  if (key === KEY_ESCAPE) return { close: true }
  if (modifiers & (CTRL | ALT | META)) return null  // leave shortcuts alone
  if (BY_KEY[key] !== undefined) return { control: BY_KEY[key] }
  var t = String(text || "")
  if (t === "p") return { link: "play" }
  if (t === "q") return { link: "queue" }
  if (t === "u") return { queueList: true }
  if (t === "d") return { details: true }
  if (t === "D") return { wholePlot: true }
  if (BY_TEXT[t] !== undefined) return { control: BY_TEXT[t] }
  return null
}
