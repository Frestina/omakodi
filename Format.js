.pragma library

// Display helpers shared by the bar widget and the remote. Pure functions.

// 393 -> "6:33", 3725 -> "1:02:05"
function time(seconds) {
  var s = Math.max(0, Math.floor(Number(seconds) || 0))
  var h = Math.floor(s / 3600)
  var m = Math.floor((s % 3600) / 60)
  var sec = s % 60
  var pad = function(n) { return n < 10 ? "0" + n : String(n) }
  return h > 0 ? h + ":" + pad(m) + ":" + pad(sec) : m + ":" + pad(sec)
}

// "6:33 / 50:09", or just the position when the length is unknown (streams).
function progress(playing) {
  if (!playing) return ""
  return playing.durationSec > 0
    ? time(playing.positionSec) + " / " + time(playing.durationSec)
    : time(playing.positionSec)
}

// The local time, "HH:MM" (24 h), `seconds` from `nowMs`: when a video ends.
function endsAt(seconds, nowMs) {
  var d = new Date(Number(nowMs) + Math.max(0, Number(seconds) || 0) * 1000)
  var pad = function(n) { return n < 10 ? "0" + n : String(n) }
  return pad(d.getHours()) + ":" + pad(d.getMinutes())
}

// Where a playing video is now: `base` seconds `elapsedMs` ago at `speed`,
// kept within 0 and the length (when known).
function livePosition(base, elapsedMs, speed, durationSec) {
  var pos = Number(base) + Math.max(0, Number(elapsedMs) || 0) / 1000 * (Number(speed) || 0)
  if (durationSec > 0) pos = Math.min(pos, durationSec)
  return Math.max(0, pos)
}

// Shortens to at most `max` characters (code points), ending in "…".
function elide(text, max) {
  var chars = Array.from(String(text || ""))
  if (max <= 0) return ""
  if (chars.length <= max) return chars.join("")
  return chars.slice(0, Math.max(1, max - 1)).join("").replace(/\s+$/, "") + "…"
}
