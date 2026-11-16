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
      muted: msg.muted === true
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

function request(id, cmd, fields) {
  var req = { id: id, cmd: cmd }
  for (var k in fields) req[k] = fields[k]
  return JSON.stringify(req) + "\n"
}
