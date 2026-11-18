---
id: 036
title: The remote's header shows the whole fix when Kodi isn't answering
milestone: M5
depends_on: [029, 035]
---

## Goal

While Kodi isn't answering, the header's text was one block cut at 4
lines, so a two-line error pushed the fix ("Is Kodi on, and is this
computer on the same network?") off the end (found 2026-11-18 while
showing the "Wake Kodi" button).

## Scope

- SPEC first.
- The header shows three parts while Kodi isn't answering: "Kodi isn't
  answering", the error cut to 2 lines, and the fix in full.

## Done when

- [x] The remote with a long error shows the fix whole (a shell preview
      against a Kodi that isn't there).
      *2026-11-18: two-line error, the fix whole under it; opened and
      closed the remote 4 times, no QML errors in the journal.*
- [x] The user has looked at it. *2026-11-18: "looks good".*
