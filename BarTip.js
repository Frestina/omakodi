.pragma library

// The bar widget's tooltip (SPEC "Bar widget"). Pure, so it can be checked
// without the shell.

// The box in use's name when there are several boxes, else "". `boxes`:
// the state's {current (the box's id), list}.
function boxName(boxes) {
  var list = boxes && boxes.list ? boxes.list : []
  if (list.length < 2) return ""
  for (var i = 0; i < list.length; i++)
    if (list[i].id === boxes.current) return String(list[i].name || list[i].host || "")
  return ""
}

// The tooltip's lines. `s`: {error (the state's: the message, then the fix
// on the next line), playing, paused, boxes}; `when`: the time line
// (Format.progress); `words`: {idle, paused, click}. The error as the
// remote's top bar says it: message and fix, nothing in front of them.
function lines(s, when, words) {
  var out = []
  var error = s && s.error ? String(s.error).trim() : ""
  var playing = s ? s.playing : null
  if (error) {
    error.split("\n").forEach(function(l) { if (l.trim() !== "") out.push(l.trim()) })
  } else if (!playing) {
    out.push(words.idle)
  } else {
    if (playing.title) out.push(playing.title)
    if (playing.subtitle) out.push(playing.subtitle)
    out.push(s.paused ? when + " · " + words.paused : when)
  }
  // With several boxes, which one this is (the error's message may name it).
  var box = boxName(s ? s.boxes : null)
  if (box && !(error && out[0].indexOf(box) >= 0)) out.unshift(box)
  out.push(words.click)
  return out
}
