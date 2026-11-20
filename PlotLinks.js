.pragma library

// The web links in the Details dialog's plot (SPEC "Details"), as a phone
// remote's details show them: the plot stays plain text, only its http and
// https links become links, which open in the browser, and Kodi's bold,
// italics and colours (the daemon's plotStyles) are drawn. Pure, so it can
// be checked without the shell.

var MAX_URL = 4096
// What ends a sentence rather than the link, when it is the last character.
var TRAILING = ".,;:!?…*"
var CLOSING = { ")": "(", "]": "[", "}": "{" }

function count(s, c) {
  return s.split(c).length - 1
}

// The link without what follows it in the sentence: a full stop, a comma …,
// and a closing bracket that has no opening one in the link ("(see
// https://example.com/a)" ends at "a", a Wikipedia link keeps its "(film)").
function trimLink(url) {
  var s = String(url)
  for (;;) {
    var last = s.charAt(s.length - 1)
    if (s.length && TRAILING.indexOf(last) >= 0) s = s.slice(0, -1)
    else if (CLOSING.hasOwnProperty(last) && count(s, last) > count(s, CLOSING[last])) s = s.slice(0, -1)
    else return s
  }
}

// Whether `url` is a link the remote opens: http or https only, with a host,
// no spaces or control characters, at most MAX_URL characters.
function isWebLink(url) {
  if (typeof url !== "string" || url.length > MAX_URL) return false
  if (/[\s\x00-\x1f\x7f-\x9f<>"']/.test(url)) return false
  var m = /^https?:\/\/([^\/?#\\]*)/i.exec(url)
  if (!m) return false
  var host = m[1].replace(/^[^@]*@/, "")  // without a user part
  return /[0-9A-Za-z¡-￿]/.test(host) && host.charAt(0) !== "."
}

// The plot cut into parts {text, url}: url is "" for plain text, else the
// link, which is also its text. Joined, the texts give the plot back.
function parts(plot) {
  var s = typeof plot === "string" ? plot : ""
  var out = []
  var at = 0
  // A link starts with http:// or https:// (ASCII, any case) and runs up
  // to a space or a character a link never has. A literal, so each call has
  // its own (Qt's RegExp.source doesn't round-trip "\/").
  var re = /[hH][tT][tT][pP][sS]?:\/\/[^\s<>"']+/g
  var m
  while ((m = re.exec(s)) !== null) {
    var url = trimLink(m[0])
    if (!isWebLink(url)) continue
    if (m.index > at) out.push({ text: s.slice(at, m.index), url: "" })
    out.push({ text: url, url: url })
    at = m.index + url.length
    re.lastIndex = at  // what was trimmed is text again
  }
  if (at < s.length) out.push({ text: s.slice(at), url: "" })
  return out
}

// The links of `parts`, in order: link i of the dialog is links(parts)[i].
function links(list) {
  var out = []
  for (var i = 0; i < (list ? list.length : 0); i++) if (list[i].url) out.push(list[i].url)
  return out
}

// Where link `index` starts in the shown text (a line break is one
// character there too), or -1.
function offset(list, index) {
  var at = 0, seen = 0
  for (var i = 0; i < (list ? list.length : 0); i++) {
    if (list[i].url) {
      if (seen === index) return at
      seen++
    }
    at += list[i].text.length
  }
  return -1
}

// Plain text for Qt's rich text: every character that could be markup is
// escaped, line breaks become <br>.
function escapeText(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;").replace(/\n/g, "<br>")
}

// A colour for the markup: "#rrggbb" from a QML colour's r, g, b (0–1).
function css(color) {
  if (!color) return "#000000"
  var out = "#"
  var channels = [color.r, color.g, color.b]
  for (var i = 0; i < 3; i++) {
    var v = Math.round(Math.max(0, Math.min(1, Number(channels[i]) || 0)) * 255)
    out += (v < 16 ? "0" : "") + v.toString(16)
  }
  return out
}

function safeColor(c, fallback) {
  return typeof c === "string" && /^#[0-9a-fA-F]{6}$/.test(c) ? c : fallback
}

// How bright "#rrggbb" looks: WCAG's relative luminance, 0 (black) to 1
// (white).
function luminance(hex) {
  var out = 0, weights = [0.2126, 0.7152, 0.0722]
  for (var i = 0; i < 3; i++) {
    var c = parseInt(hex.substr(1 + 2 * i, 2), 16) / 255
    out += weights[i] * (c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4))
  }
  return out
}

// WCAG's contrast ratio of two "#rrggbb" colours: 1 (the same) to 21.
function contrast(a, b) {
  var la = luminance(a), lb = luminance(b)
  return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05)
}

// What WCAG asks of body text.
var READABLE = 4.5

// "#rrggbb" as hue (0–360), saturation and lightness (0–1), and back.
function toHsl(hex) {
  var r = parseInt(hex.substr(1, 2), 16) / 255, g = parseInt(hex.substr(3, 2), 16) / 255,
      b = parseInt(hex.substr(5, 2), 16) / 255
  var max = Math.max(r, g, b), min = Math.min(r, g, b), l = (max + min) / 2, d = max - min
  if (d === 0) return { h: 0, s: 0, l: l }
  var s = d / (1 - Math.abs(2 * l - 1))
  var h = max === r ? ((g - b) / d) % 6 : max === g ? (b - r) / d + 2 : (r - g) / d + 4
  return { h: (h * 60 + 360) % 360, s: s, l: l }
}

function fromHsl(h, s, l) {
  var c = (1 - Math.abs(2 * l - 1)) * s, x = c * (1 - Math.abs((h / 60) % 2 - 1)), m = l - c / 2
  var rgb = h < 60 ? [c, x, 0] : h < 120 ? [x, c, 0] : h < 180 ? [0, c, x]
          : h < 240 ? [0, x, c] : h < 300 ? [x, 0, c] : [c, 0, x]
  return css({ r: rgb[0] + m, g: rgb[1] + m, b: rgb[2] + m })
}

// `color` (Kodi's "#rrggbb") as it reads on `background` (the dialog's
// "#rrggbb"): as it is when its contrast is READABLE or more, else darker
// on a light background or lighter on a dark one, just enough, with its
// hue and saturation kept. Anything but two "#rrggbb" gives `color` back.
function readable(color, background) {
  if (!/^#[0-9a-fA-F]{6}$/.test(color) || !/^#[0-9a-fA-F]{6}$/.test(background)) return color
  if (contrast(color, background) >= READABLE) return color
  var hsl = toHsl(color)
  // Towards black or white, whichever stands out more on the background:
  // that end always reads (at least 4.58:1).
  var end = contrast("#000000", background) >= contrast("#ffffff", background) ? 0 : 1
  var near = hsl.l, far = end
  for (var i = 0; i < 24; i++) {  // the lightness nearest the colour's that reads
    var mid = (near + far) / 2
    if (contrast(fromHsl(hsl.h, hsl.s, mid), background) >= READABLE) far = mid
    else near = mid
  }
  var out = fromHsl(hsl.h, hsl.s, far)
  return contrast(out, background) >= READABLE ? out : (end ? "#ffffff" : "#000000")
}

// `parts` cut where a style of `styles` (Protocol.js plotStyles: {from, to,
// bold, italic, color}, in order, not overlapping) starts or ends: pieces
// {text, link, bold, italic, color}, link the index of the link the piece
// is in or -1. Joined, the texts give the plot back.
function pieces(list, styles) {
  var out = []
  var st = Array.isArray(styles) ? styles : []
  var at = 0, seen = 0, si = 0
  for (var i = 0; i < (list ? list.length : 0); i++) {
    var p = list[i]
    var start = at, end = at + p.text.length
    var link = p.url ? seen++ : -1
    while (at < end) {
      while (si < st.length && !(st[si] && st[si].to > at)) si++
      var s = si < st.length ? st[si] : null
      var inside = s !== null && s.from <= at
      var next = s === null ? end : Math.min(end, inside ? s.to : s.from)
      if (!(next > at)) next = end  // a broken style: the rest plain
      out.push({ text: p.text.slice(at - start, next - start), link: link,
                 bold: inside && s.bold === true, italic: inside && s.italic === true,
                 color: inside ? safeColor(s.color, "") : "" })
      at = next
    }
    at = end
  }
  return out
}

// The plot as rich text: all of it escaped, but for the links, which are
// <a href="N"> (N their index, never the URL itself) in `linkColor` and
// underlined; the `focused` one (Tab) is drawn in `focusedColor` on the
// link colour. `styles` adds Kodi's bold (<b>), italics (<i>) and colours
// (<span style="color:#rrggbb">, checked again here); with `background`
// (the dialog's "#rrggbb") each colour is made readable() on it. A link
// keeps the link colour. White space and line breaks stay as they are.
function markup(list, focused, linkColor, focusedColor, styles, background) {
  var link = safeColor(linkColor, "#3584e4")
  var onLink = safeColor(focusedColor, "#ffffff")
  var under = safeColor(background, "")
  var shown = {}  // Kodi's colour → the one drawn
  var out = '<div style="white-space:pre-wrap;line-height:120%">'
  var all = pieces(list, styles)
  for (var i = 0; i < all.length; i++) {
    var p = all[i]
    if (p.color && under) {
      if (!shown.hasOwnProperty(p.color)) shown[p.color] = safeColor(readable(p.color, under), "")
      p.color = shown[p.color]
    }
    var text = escapeText(p.text)
    if (p.italic) text = "<i>" + text + "</i>"
    if (p.bold) text = "<b>" + text + "</b>"
    if (p.link < 0) {
      out += p.color ? '<span style="color:' + p.color + '">' + text + "</span>" : text
    } else if (p.link === focused) {
      out += '<a href="' + p.link + '" style="color:' + onLink + ';background-color:' + link
        + ';text-decoration:underline">' + text + '</a>'
    } else {
      out += '<a href="' + p.link + '" style="color:' + link + ';text-decoration:underline">' + text + '</a>'
    }
  }
  return out + "</div>"
}

// The link a click names: its index ("0", "1" … from markup()), or -1.
function linkIndex(href, total) {
  var s = String(href)
  if (!/^\d{1,4}$/.test(s)) return -1
  var n = parseInt(s, 10)
  return n < total ? n : -1
}

// Tab (`step` 1) and Shift+Tab (-1): the next or previous link, round the
// end; -1 without links.
function step(total, current, dir) {
  if (!(total > 0)) return -1
  if (current < 0 || current >= total) return dir < 0 ? total - 1 : 0
  return ((current + (dir < 0 ? -1 : 1)) % total + total) % total
}

// The command that opens `url` in the default browser: xdg-open with the
// link as its one argument (no shell), or null for anything but a web link.
function openCommand(url) {
  return isWebLink(url) ? ["xdg-open", url] : null
}
