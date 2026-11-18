.pragma library

// The daemon's JSON lines (SPEC "Daemon protocol"), checked field by field.
// Everything that reaches the QML is a plain value of a known type and size;
// the views show strings as plain text.

var MAX_LINE = 64 * 1024
var MAX_TEXT = 300
var MAX_LINK_TEXT = 8 * 1024

var ACTIONS = ["up", "down", "left", "right", "select", "back", "info", "context", "osd",
               "home", "volup", "voldown", "mute", "fullscreen", "playpause", "stop",
               "next", "previous", "rewind", "fastforward", "playerinfo", "powermenu",
               "reboot", "shutdown"]
var MAX_SEEK = 7 * 24 * 3600  // lib/omakodi/control.py MAX_SEEK

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
    // 1 normal, 0 paused, 2/4/… fast-forward, -2/… rewind
    speed: typeof p.speed === "number" && Math.floor(p.speed) === p.speed && Math.abs(p.speed) <= 64
      ? p.speed : (p.paused === true ? 0 : 1),
    art: artPath(p.art),
    positionSec: count(p.positionSec),
    durationSec: count(p.durationSec)
  }
}

// The video queue while it plays, or null: the playing position, where the
// shown window starts, the total, and up to 100 entries' titles.
var MAX_QUEUE = 100000  // lib/omakodi/control.py MAX_QUEUE
function queue(q) {
  if (!q || typeof q !== "object" || !Array.isArray(q.items)) return null
  var items = q.items.slice(0, 100).map(function(i) {
    i = i && typeof i === "object" ? i : {}
    return { title: text(i.title), subtitle: text(i.subtitle) }
  })
  var start = count(q.start)
  return {
    position: count(q.position),
    start: start,
    total: Math.max(count(q.total), start + items.length),
    items: items
  }
}

// What Kodi knows about the playing item (SPEC "Details"), or null. Every
// field is there, empty when Kodi doesn't know it; the plot keeps its line
// breaks.
function names(value, n, limit) {
  if (!Array.isArray(value)) return []
  return value.filter(function(v) { return typeof v === "string" && v !== "" })
    .slice(0, n).map(function(v) { return text(v, limit) })
}

function details(d) {
  if (!d || typeof d !== "object" || Array.isArray(d)) return null
  var year = typeof d.year === "number" && Math.floor(d.year) === d.year && d.year >= 1800 && d.year <= 2200
    ? d.year : 0
  return {
    plot: text(d.plot, 3000),
    genres: names(d.genres, 5, 40),
    year: year,
    studio: text(d.studio, 120),
    rating: /^(?:10\.0|[0-9]\.[0-9])$/.test(text(d.rating, 4)) ? d.rating : "",
    cast: names(d.cast, 10, 60),
    badges: names(d.badges, 4, 20)
  }
}

// The playing item's audio tracks, or null: the playing track's index
// (-1: not listed) and up to 32 tracks.
var MAX_AUDIO_INDEX = 999  // lib/omakodi/audio.py MAX_INDEX
function audioIndex(value) {
  return typeof value === "number" && Math.floor(value) === value && value >= 0 && value <= MAX_AUDIO_INDEX
    ? value : -1
}

function audio(a) {
  if (!a || typeof a !== "object" || !Array.isArray(a.tracks)) return null
  var seen = {}
  var tracks = []
  a.tracks.slice(0, 32).forEach(function(t) {
    t = t && typeof t === "object" ? t : {}
    var index = audioIndex(t.index)
    if (index < 0 || seen[index]) return
    seen[index] = true
    tracks.push({ index: index, name: text(t.name, 100), language: text(t.language, 40),
                  codec: text(t.codec, 20), channels: text(t.channels, 20) })
  })
  if (tracks.length === 0) return null
  var current = audioIndex(a.current)
  return { current: seen[current] ? current : -1, tracks: tracks }
}

// What Kodi allows and whether it is on, or null before Kodi has said.
var POWER_STATES = ["on", "off", "restarting"]
function power(p) {
  if (!p || typeof p !== "object") return null
  return {
    state: POWER_STATES.indexOf(p.state) >= 0 ? p.state : "on",
    reboot: p.reboot === true,
    shutdown: p.shutdown === true
  }
}

// A local image the daemon cached: an absolute path to a .jpg/.png/.webp in
// an "omakodi/art" folder, no "..", no URL. Anything else: "".
function artPath(value) {
  var s = text(value, 1024)
  return /^\/(?:[^\/\n]+\/)*omakodi\/art\/[0-9a-f]{32}\.(?:jpg|png|webp)$/.test(s) && s.indexOf("/../") < 0
    ? s : ""
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
      queue: queue(msg.queue),
      details: details(msg.details),
      audio: audio(msg.audio),
      power: power(msg.power),
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
