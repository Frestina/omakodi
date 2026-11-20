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
               "reboot", "shutdown", "soundbaron", "soundbarup", "soundbardown"]
var MAX_SEEK = 7 * 24 * 3600  // lib/omakodi/control.py MAX_SEEK
var VOLUME_KEYS = ["kodi", "tv", "unknown"]  // where Kodi's volume keys go (SPEC "Volume")
var YOUTUBE_MODES = ["smart", "youtube-first", "sendtokodi-only", "youtube-only"]  // lib/omakodi/config.py

// The YouTube mode in use (SPEC "Daemon protocol"), or null.
function youtube(y) {
  if (!y || typeof y !== "object") return null
  var until = typeof y.avoidUntil === "number" && isFinite(y.avoidUntil) && y.avoidUntil > 0 ? Math.floor(y.avoidUntil) : 0
  return {
    mode: YOUTUBE_MODES.indexOf(y.mode) >= 0 ? y.mode : "smart",
    from: y.from === "remote" ? "remote" : "config",
    avoidUntil: until,
    box: text(y.box, 253)
  }
}

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
// breaks. Info rows of an unknown kind are left out; a cast photo is a local
// file the daemon cached (artPath) or "".
var INFO_KINDS = ["channel", "genre", "show", "date", "studio", "rating", "age", "runtime",
                  "director", "writer", "country"]  // lib/omakodi/details.py INFO_KINDS

function names(value, n, limit) {
  if (!Array.isArray(value)) return []
  return value.filter(function(v) { return typeof v === "string" && v !== "" })
    .slice(0, n).map(function(v) { return text(v, limit) })
}

// Where the plot is bold, italic or coloured (SPEC "Details"): stretches of
// the plot in order, never overlapping, each with a style; a colour only
// ever "#rrggbb".
var MAX_STYLES = 200  // lib/omakodi/details.py MAX_STYLES
function plotStyles(value, length) {
  var out = []
  var end = 0
  var list = Array.isArray(value) ? value.slice(0, MAX_STYLES) : []
  for (var i = 0; i < list.length; i++) {
    var s = list[i]
    if (!s || typeof s !== "object") continue
    var from = s.from
    if (typeof from !== "number" || typeof s.to !== "number" || Math.floor(from) !== from
        || Math.floor(s.to) !== s.to) continue
    var to = Math.min(s.to, length)
    if (from < end || to <= from) continue
    var color = typeof s.color === "string" && /^#[0-9a-f]{6}$/.test(s.color) ? s.color : ""
    if (s.bold !== true && s.italic !== true && color === "") continue
    out.push({ from: from, to: to, bold: s.bold === true, italic: s.italic === true, color: color })
    end = to
  }
  return out
}

function details(d) {
  if (!d || typeof d !== "object" || Array.isArray(d)) return null
  var info = (Array.isArray(d.info) ? d.info : []).filter(function(r) {
    return r && typeof r === "object" && INFO_KINDS.indexOf(r.kind) >= 0 && typeof r.text === "string" && r.text !== ""
  }).slice(0, INFO_KINDS.length).map(function(r) { return { kind: r.kind, text: text(r.text) } })
  var cast = (Array.isArray(d.cast) ? d.cast : []).filter(function(c) {
    return c && typeof c === "object" && typeof c.name === "string" && c.name !== ""
  }).slice(0, 20).map(function(c) {
    return { name: text(c.name, 60), role: text(c.role, 60), photo: artPath(c.photo) }
  })
  var plot = text(d.plot, 5000)
  return {
    title: text(d.title),
    subtitle: text(d.subtitle),
    plot: plot,
    plotStyles: plotStyles(d.plotStyles, plot.length),
    badges: names(d.badges, 5, 20),
    info: info,
    cast: cast
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

// The box's five shortcut buttons (SPEC "Shortcut buttons"), or null:
// labels, icon names and local art files only.
var SLOTS = 5
var ICON_NAME = /^[a-z0-9_]{1,30}$/
function button(b) {
  b = b && typeof b === "object" ? b : {}
  return {
    label: text(b.label, 150),
    sendLink: b.sendLink === true,
    icon: ICON_NAME.test(text(b.icon, 30)) ? b.icon : "",
    art: artPath(b.art),
    auto: ICON_NAME.test(text(b.auto, 30)) ? b.auto : "folder",
    custom: b.custom === true,
    typed: text(b.typed, 2048)
  }
}

function shortcuts(s) {
  if (!s || typeof s !== "object" || !Array.isArray(s.buttons) || s.buttons.length !== SLOTS) return null
  return { box: text(s.box, 253), buttons: s.buttons.map(button) }
}

// A page of the "Choose from Kodi" picker.
var MAX_ROWS = 500  // lib/omakodi/shortcuts.py MAX_ROWS
var PICKER_STATUS = ["loading", "ready", "failed"]
function picker(p) {
  var items = Array.isArray(p.items) ? p.items.slice(0, MAX_ROWS) : []
  return {
    type: "picker",
    seq: count(p.seq),
    title: text(p.title),
    crumb: text(p.crumb),
    folder: p.folder === true,
    depth: Math.max(1, count(p.depth)),
    status: PICKER_STATUS.indexOf(p.status) >= 0 ? p.status : "failed",
    error: text(p.error),
    items: items.map(function(i) {
      i = i && typeof i === "object" ? i : {}
      return { label: text(i.label, 150), detail: text(i.detail, 150), browse: i.browse === true }
    })
  }
}

// The Kodi boxes (SPEC "Kodi boxes"): the one in use and each box's
// settings, never a password (only whether one is saved).
var MAX_BOXES = 32  // lib/omakodi/config.py MAX_BOXES
var MAC_RE = /^[0-9a-f]{2}(:[0-9a-f]{2}){5}$/
function port(value, fallback) {
  return typeof value === "number" && Math.floor(value) === value && value >= 1 && value <= 65535 ? value : fallback
}
function boxes(b) {
  if (!b || typeof b !== "object" || !Array.isArray(b.list)) return { current: "", list: [] }
  var list = b.list.slice(0, MAX_BOXES).filter(function(x) {
    return x && typeof x === "object" && typeof x.host === "string" && x.host !== ""
  }).map(function(x) {
    return {
      name: text(x.name, 100) || text(x.host, 253),
      host: text(x.host, 253),
      httpPort: port(x.httpPort, 8080),
      tcpPort: port(x.tcpPort, 9090),
      username: text(x.username, 100),
      hasPassword: x.hasPassword === true,
      mac: MAC_RE.test(text(x.mac, 17)) ? x.mac : "",
      knownMac: MAC_RE.test(text(x.knownMac, 17)) ? x.knownMac : ""
    }
  })
  return { current: text(b.current, 253), list: list }
}

// "Found on your network": a search's state and the boxes it found that
// aren't saved.
var FOUND_STATUS = ["searching", "done", "failed"]
function found(f) {
  var list = Array.isArray(f.boxes) ? f.boxes.slice(0, 20) : []
  return {
    type: "found",
    status: FOUND_STATUS.indexOf(f.status) >= 0 ? f.status : "failed",
    error: text(f.error),
    total: count(f.total),  // found at all, saved ones too
    boxes: list.filter(function(x) { return x && typeof x === "object" && typeof x.host === "string" && x.host !== "" })
      .map(function(x) {
        return { name: text(x.name, 100) || text(x.host, 253), host: text(x.host, 253),
                 httpPort: port(x.httpPort, 8080), tcpPort: port(x.tcpPort, 9090) }
      })
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
      queue: queue(msg.queue),
      details: details(msg.details),
      audio: audio(msg.audio),
      power: power(msg.power),
      wake: msg.wake === true,
      wakeOnLan: msg.wakeOnLan !== false,
      volumeKeys: VOLUME_KEYS.indexOf(msg.volumeKeys) >= 0 ? msg.volumeKeys : "unknown",
      youtube: youtube(msg.youtube),
      shortcuts: shortcuts(msg.shortcuts),
      input: input(msg.input),
      boxes: boxes(msg.boxes),
      connecting: msg.connecting === true
    }
  }
  if (msg.type === "picker") return picker(msg)
  if (msg.type === "found") return found(msg)
  if (msg.type === "boxTest") {
    if (typeof msg.id !== "number") return null
    return { type: "boxTest", id: msg.id, name: text(msg.name, 100),
             mac: MAC_RE.test(text(msg.mac, 17)) ? msg.mac : "" }
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
  return extractLink(value) !== ""
}

// The link `omakodi play` would take from the text, or "".
function extractLink(value) {
  var m = LINK_RE.exec(String(value || ""))
  if (!m) return ""
  var url = m[0].replace(/[.,;!)]+$/, "")
  var points = 0
  for (var i = 0; i < url.length; i++) {
    var c = url.charCodeAt(i)
    if (c < 0xdc00 || c > 0xdfff || i === 0 || url.charCodeAt(i - 1) < 0xd800 || url.charCodeAt(i - 1) > 0xdbff) points++
  }
  return points <= MAX_URL ? url : ""  // Python counts code points, not UTF-16 units
}

function request(id, cmd, fields) {
  var req = { id: id, cmd: cmd }
  for (var k in fields) req[k] = fields[k]
  return JSON.stringify(req) + "\n"
}
