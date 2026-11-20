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
  "<": "rewind", ">": "fastforward",  // one key on a Nordic keyboard, Shift for >
  "I": "playerinfo",  // Shift+i: Kodi's player process info
  "s": "soundbaron",  // turn on the soundbar over HDMI-CEC
  "9": "soundbardown", "0": "soundbarup"  // Kodi's volume keys (CEC)
}

// Returns {close: true}, {control: "<action>"}, {link: "play"|"queue"},
// {queueList: true} (show or hide the queue), {details: true} (show or hide
// the Details dialog), {audioList: true} (show or hide
// the audio tracks), {nowPlaying: true} (open or close the now-playing page),
// {powerMenu: true}, {wake: true} (Wake up, as in the power menu),
// {settings: true}, {boxes: true}, {menu: true} (the ☰ menu), {keyboard: true}
// (Type text), {shortcut: 0-4} (open a strip button), {editStrip: true}
// (the next key, 1-5, picks the button to change) or null.
function lookup(key, text, modifiers) {
  if (key === KEY_ESCAPE) return { close: true }
  if (modifiers & (CTRL | ALT | META)) return null  // leave shortcuts alone
  if (BY_KEY[key] !== undefined) return { control: BY_KEY[key] }
  var t = String(text || "")
  if (t === "p") return { link: "play" }
  if (t === "q") return { link: "queue" }
  if (t === "u") return { queueList: true }
  if (t === "d") return { details: true }
  if (t === "a") return { audioList: true }
  if (t === "n") return { nowPlaying: true }
  if (t === "P") return { powerMenu: true }  // only opens it: reboot and shut down ask again
  if (t === "w") return { wake: true }
  if (t === "S") return { settings: true }  // Shift+s: the Settings page
  if (t === "b") return { boxes: true }  // the Kodi boxes page
  if (t === "M") return { menu: true }  // Shift+m: the ☰ menu
  if (t === "k") return { keyboard: true }  // Type text, as the action row's keyboard key
  if (t === "e") return { editStrip: true }
  var slot = stripSlot(t)
  if (slot >= 0) return { shortcut: slot }
  if (BY_TEXT[t] !== undefined) return { control: BY_TEXT[t] }
  return null
}

// The strip button a key names: "1" to "5" from the left, else -1. After
// "e", the next key picks the button to change this way.
function stripSlot(text) {
  var t = String(text || "")
  return t.length === 1 && t >= "1" && t <= "5" ? t.charCodeAt(0) - 49 : -1
}

// The action row, in the phone remote's order: the audio tracks (a list,
// not an action), fullscreen, info, the keyboard key (Type text, not an
// action) and Kodi's player info. Home is on the strip; the context menu
// is a long press of OK (and a right click, and c).
var ACTION_ROW = ["audio", "fullscreen", "info", "keyboard", "playerinfo"]

// Keys held with the mouse repeat like a real remote's: the first press at
// once, again after REPEAT_DELAY ms, then every REPEAT_INTERVAL ms. Each
// repeat goes only once Kodi has answered the last key (Service.key).
var REPEAT_DELAY = 400
var REPEAT_INTERVAL = 110
var HELD_REPEATS = ["up", "down", "left", "right", "voldown", "volup"]
// Holding OK this long opens the context menu instead (as the strip's 0.5 s).
var LONG_PRESS = 500

function repeats(action) { return HELD_REPEATS.indexOf(action) >= 0 }

// Keys that send once per press however long they are held, with the mouse
// and on the keyboard (its auto-repeats are dropped): the soundbar's steps
// (the user's choice) and mute (a held mute would only flip back and forth).
var ONCE_PER_PRESS = ["soundbardown", "soundbarup", "mute"]

function oncePerPress(action) { return ONCE_PER_PRESS.indexOf(action) >= 0 }

// When the repeats of a key held from 0 ms are sent, up to `untilMs`.
function repeatTimes(untilMs) {
  var out = []
  for (var t = REPEAT_DELAY; t <= untilMs; t += REPEAT_INTERVAL) out.push(t)
  return out
}
