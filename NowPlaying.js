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
