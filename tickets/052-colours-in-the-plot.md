---
id: 052
title: Bold, italics and colours in the plot like the phone remote
milestone: M7
depends_on: [046, 049]
---

## Goal

The Details overview shows Kodi's formatting as the phone remote does,
instead of plain text. The user (2026-11-20): "same as" the phone.

## Scope

- SPEC first: "Details" and the rule that external text is plain (049
  made links the one exception; this adds Kodi's own tags).
- `[B]` bold, `[I]` italic, `[COLOR=x]` and `[COLOR x]` with a hex colour
  (AARRGGBB or RRGGBB, an optional `#` or `0x`) or one of Kodi's common
  colour names; an unknown colour: the text without a colour. `[CR]` a
  line break. `[LIGHT]`, `[UPPERCASE]`, `[LOWERCASE]`, `[CAPITALIZE]`,
  `[TABS]` removed with no effect. A closing tag ends its own opening
  tag. Links stay as in 049.
- omakodi still removes other tags it doesn't know (the phone leaves them
  in the text by mistake; its own notes say they are meant to go).
- Safety: the remote builds all markup itself; the plot's text is
  escaped, and a colour is only ever a checked hex value.
- Single-line labels (titles, stream names) stay plain: tags removed,
  `[CR]` a space.

## Done when

- [x] Unit tests: each tag, nested and unclosed tags, colour forms and
      names, unknown colours and tags, escaping, links still working.
- [x] Live, by the user: a plot with bold and colours looks like the
      phone's. *2026-11-20: the user's check passes.*
