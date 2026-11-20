---
id: 049
title: Links in the details like the phone remote
milestone: M7
depends_on: [046]
---

## Goal

Web links in the Details dialog's Overview can be clicked, as they can
be tapped on the user's phone remote. Found in the user's check of 046
(2026-11-19): "only missing things being a links".

## Scope

- SPEC first: "Details" and the rule that external text is plain. Links
  are the one exception; everything else in the plot stays plain text.
- Find the web links (`http://`, `https://`) in the plot, YouTube
  descriptions included, and show them as links (accent colour). Other
  text is never turned into markup.
- A click does what the phone remote's tap does (read how it does it
  first). On a laptop that is most likely opening the link in the
  default browser (`xdg-open`, the URL as one argument, never through a
  shell). If the phone also offers playing a link on Kodi, offer the
  same.
- The keyboard can reach and open links too (e.g. Tab to the next link,
  Enter opens it).
- Only `http`/`https` links open; anything else stays text.

## Done when

- [x] Unit tests: links found in plots (several, at the end of a line,
      with punctuation after them, none), other text left plain, only
      http/https accepted.
- [x] Live, by the user: a YouTube video's description with links; a
      click (and the keyboard) opens the link as on the phone. *2026-11-20: the user's check passes.*
