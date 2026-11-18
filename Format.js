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

// The now-playing page's clock: with hours whenever the length is an hour
// or more, so elapsed and total read alike ("0:05:12" of "1:47:20").
function clock(seconds, totalSec) {
  var s = Math.max(0, Math.floor(Number(seconds) || 0))
  if (Number(totalSec) >= 3600 && s < 3600) {
    var pad = function(n) { return n < 10 ? "0" + n : String(n) }
    return "0:" + pad(Math.floor(s / 60)) + ":" + pad(s % 60)
  }
  return time(s)
}

// The middle of the page's time row: "" at normal speed, `pausedText` while
// paused, else `speedText` with %1 the speed ("Speed: 2x", "Speed: -4x").
function speedLine(playing, pausedText, speedText) {
  if (!playing) return ""
  var speed = Number(playing.speed)
  if (playing.paused || speed === 0) return String(pausedText)
  if (speed === 1 || !isFinite(speed)) return ""
  return String(speedText).replace("%1", String(speed))
}

// The right of the page's time row: the length and when it ends at normal
// speed, `template` "%1 · ends %2" → "47:20 · ends 21:40"; "" while the
// length is unknown (live streams).
function endLine(positionSec, durationSec, nowMs, template) {
  if (!(Number(durationSec) > 0)) return ""
  return String(template).replace("%1", clock(durationSec, durationSec))
    .replace("%2", endsAt(Number(durationSec) - Math.max(0, Number(positionSec) || 0), nowMs))
}
