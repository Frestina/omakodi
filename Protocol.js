.pragma library

// The daemon's JSON lines (SPEC "Daemon protocol"), checked field by field.
// Everything that reaches the QML is a plain value of a known type and size;
// the views show strings as plain text.

var MAX_LINE = 64 * 1024
var MAX_TEXT = 300
var MAX_LINK_TEXT = 8 * 1024

var ACTIONS = ["up", "down", "left", "right", "select", "back", "info", "context", "osd",
               "home", "volup", "voldown", "mute", "fullscreen", "playpause", "stop"]

function text(value, limit) {
  return typeof value === "string" ? value.slice(0, limit || MAX_TEXT) : ""
}

function count(value) {
  return typeof value === "number" && isFinite(value) && value >= 0 ? Math.floor(value) : 0
}

function playing(p) {
  if (!p || typeof p !== "object") return null
  return {
    title: text(p.title),
    subtitle: text(p.subtitle),
    kind: text(p.kind, 20),
    paused: p.paused === true,
    positionSec: count(p.positionSec),
    durationSec: count(p.durationSec)
  }
}

// Kodi's on-screen keyboard while it is open, or null. `hidden`: show dots.
function input(i) {
  if (!i || typeof i !== "object") return null
  var type = text(i.type, 20) || "keyboard"
  return {
    type: type,
    title: text(i.title),
    value: text(i.value),
    hidden: type === "password" || type === "numericpassword"
  }
}

// Returns {type: "state"|"result"|"progress", ...} or null for anything else.
function parse(line) {
  var raw = String(line || "")
  if (raw.length === 0 || raw.length > MAX_LINE) return null
  var msg
  try { msg = JSON.parse(raw) } catch (e) { return null }
  if (!msg || typeof msg !== "object") return null
  if (msg.type === "state") {
    return {
      type: "state",
      reachable: msg.reachable === true,
      error: text(msg.error),
      playing: playing(msg.playing),
      volume: typeof msg.volume === "number" && msg.volume >= 0 && msg.volume <= 100 ? Math.round(msg.volume) : -1,
      muted: msg.muted === true,
      input: input(msg.input)
    }
  }
  if (msg.type === "result" || msg.type === "progress") {
    if (typeof msg.id !== "number") return null  // the service only sends numbers
    return {
      type: msg.type,
      id: msg.id,
      ok: msg.type === "progress" || msg.ok === true,
      message: text(msg.message),
      error: text(msg.error)
    }
  }
  return null
}

// Whether `omakodi play`/`queue` would find a link in the text: the same
// yes/no as extract_url() in lib/omakodi/links.py, so the service can answer
// "no link found" at once. Spelled out instead of /\s/ and the i flag, which
// differ from Python's: Python's \s also has \x1c-\x1f and \x85 but not
// \ufeff, and its re.I lets "\u017f" (U+017F) match "s".
var MAX_URL = 4096
var LINK_RE = /[hH][tT][tT][pP][sS\u017f]?:\/\/[^\t\n\v\f\r \x1c-\x1f\x85\xa0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000<>"']+/

function hasLink(value) {
  var m = LINK_RE.exec(String(value || ""))
  if (!m) return false
  var url = m[0].replace(/[.,;!)]+$/, "")
  var points = 0
  for (var i = 0; i < url.length; i++) {
    var c = url.charCodeAt(i)
    if (c < 0xdc00 || c > 0xdfff || i === 0 || url.charCodeAt(i - 1) < 0xd800 || url.charCodeAt(i - 1) > 0xdbff) points++
  }
  return points <= MAX_URL  // Python counts code points, not UTF-16 units
}

function request(id, cmd, fields) {
  var req = { id: id, cmd: cmd }
  for (var k in fields) req[k] = fields[k]
  return JSON.stringify(req) + "\n"
}
