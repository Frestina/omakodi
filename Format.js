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

// Shortens to at most `max` characters (code points), ending in "…".
function elide(text, max) {
  var chars = Array.from(String(text || ""))
  if (max <= 0) return ""
  if (chars.length <= max) return chars.join("")
  return chars.slice(0, Math.max(1, max - 1)).join("").replace(/\s+$/, "") + "…"
}
