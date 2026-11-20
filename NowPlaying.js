.pragma library

// The now-playing page and its Queue dialog (SPEC "Remote panel"). Pure, so
// they can be checked without the shell.

// The play/pause key shows pause only while it plays at normal speed, as on
// the phone remote; paused, rewinding or fast-forwarding it shows play.
function showsPause(playing) {
  return !!playing && !playing.paused && Number(playing.speed) === 1
}

// What the Queue dialog shows: "loading" while the remote waits for the
// daemon's fresh read, "empty" without entries (also when what plays isn't
// from the queue), else "ready".
function queueStatus(queue, loading) {
  if (loading) return "loading"
  if (!queue || !queue.items || queue.items.length === 0) return "empty"
  return "ready"
}

// The dialog's rows: "3. Title", the subtitle under it, the playing one
// marked (accent, bold), which can be taken out (not the playing one).
function queueRows(queue) {
  if (!queue || !queue.items) return []
  var start = Number(queue.start) || 0
  var rows = []
  for (var i = 0; i < queue.items.length; i++) {
    var item = queue.items[i] || {}
    var position = start + i
    var playing = position === queue.position
    rows.push({
      position: position,
      label: (position + 1) + ". " + (item.title ? String(item.title) : "?"),
      detail: item.subtitle ? String(item.subtitle) : "",
      playing: playing,
      removable: !playing
    })
  }
  return rows
}

// How an audio track reads (SPEC "Audio tracks"), as on the phone remote:
// "English · Director's commentary"; without Kodi's name for the stream,
// the codec and channels instead ("Norwegian · EAC3 5.1"); a part the same
// as one before it once; with nothing known `fallback` ("Audio %1") with its
// place in the list from 1.
function trackLabel(track, at, fallback) {
  var t = track && typeof track === "object" ? track : {}
  var str = function(x) { return typeof x === "string" ? x : "" }
  var name = str(t.name)
  var sound = name ? "" : [str(t.codec), str(t.channels)].filter(function(x) { return x !== "" }).join(" ")
  var candidates = [str(t.language), name, sound]
  var parts = []
  for (var i = 0; i < candidates.length; i++)
    if (candidates[i] && parts.indexOf(candidates[i]) < 0) parts.push(candidates[i])
  return parts.length ? parts.join(" · ") : String(fallback || "Audio %1").replace("%1", at + 1)
}

// The track list's rows: each track's words, the playing one marked (the
// accent colour and bold, as on the phone remote).
function audioRows(audio, fallback) {
  if (!audio || !Array.isArray(audio.tracks)) return []
  return audio.tracks.map(function(t, i) {
    return { index: t ? t.index : -1, label: trackLabel(t, i, fallback), current: !!t && t.index === audio.current }
  })
}

// Whether the audio key opens the list: for one track or more, as on the
// phone remote (ticket 055); with none it says so instead.
function audioListOpens(audio) {
  return !!audio && Array.isArray(audio.tracks) && audio.tracks.length > 0
}

// The audio key's tooltip: `title`, then the playing track's words and its
// place ("English · Commentary · 2/3"; "?" when the playing one isn't listed).
function audioKeyTip(audio, title, fallback) {
  if (!audioListOpens(audio)) return String(title)
  var at = -1
  for (var i = 0; i < audio.tracks.length; i++)
    if (audio.tracks[i] && audio.tracks[i].index === audio.current) { at = i; break }
  var words = at < 0 ? "" : trackLabel(audio.tracks[at], at, fallback) + " · "
  return String(title) + "\n" + words + (at < 0 ? "?" : at + 1) + "/" + audio.tracks.length
}

// The remote's actions that work on the page: what its buttons do, and the
// volume keys (a phone's volume buttons work on every page).
var PAGE_CONTROLS = ["playpause", "rewind", "fastforward", "next", "previous", "volup", "voldown", "mute"]

// A key on the page: the RemoteKeys.lookup hit when it works there, else
// null (the page has no D-pad: the arrows and Enter don't reach Kodi).
// Esc and n close it, d the details, u the queue.
function pageKey(hit) {
  if (!hit) return null
  if (hit.close || hit.nowPlaying || hit.details || hit.queueList) return hit
  if (hit.control && PAGE_CONTROLS.indexOf(hit.control) >= 0) return hit
  return null
}

// The Details dialog's Info rows: each kind's icon (a Material Design Icons
// code point in the Nerd Font), as a phone remote's details show them.
var INFO_ICONS = {
  channel: 0xF0B55,   // account-circle-outline
  genre: 0xF0832,     // shape-outline
  show: 0xF0502,      // television
  date: 0xF0B67,      // calendar-outline
  studio: 0xF01D7,    // domain
  rating: 0xF04D2,    // star-outline
  age: 0xF0CC8,       // shield-check-outline
  runtime: 0xF0150,   // clock-outline
  director: 0xF0BDC,  // video-outline
  writer: 0xF0CB6,    // pencil-outline
  country: 0xF01E7    // earth
}

function infoIcon(kind) {
  return INFO_ICONS.hasOwnProperty(kind) ? INFO_ICONS[kind] : 0xF02FD  // information-outline
}
