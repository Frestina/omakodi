---
id: 016
title: IPC play and queue reject text without a link
milestone: M2
depends_on: [008]
---

## Goal

`play(text)` and `queue(text)` over IPC answer `no link found` at once when
the text has no http(s) link, as SPEC "IPC target" says, instead of `ok`
followed by the daemon's error in `lastResult`.

Found in the ticket 012 live check: `play("just words")` answered `ok`.
`Service.qml` only rejects empty text.

## Scope

- A link check in `Protocol.js` that matches `links.py` (`URL_RE`: the first
  `https?://` run of characters other than whitespace, `<`, `>`, `"`, `'`,
  case-insensitive). Used by `Service.qml` before sending.
- The daemon keeps its own check; the service's is only for the quick answer.
- The remote's `p`/`q` and its Play link / Queue link buttons go through the
  same path, so a clipboard without a link shows `no link found` at once.

## Done when

- [ ] A test that runs the `Protocol.js` check and `links.extract_url` over the
      same cases (no link, link in text, `HTTP://`, quoted, link at the end
      with trailing punctuation, `https://.`) and gets the same yes/no.
- [ ] Live, laptop only: IPC `play("just words")` answers `no link found` and
      no command reaches the daemon (`pending` stays 0, `lastResult` unchanged).
