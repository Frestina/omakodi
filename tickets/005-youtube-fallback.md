---
id: 005
title: YouTube verdict and fallback
milestone: M1
depends_on: [004]
---

## Goal

When the YouTube add-on can't play a link, omakodi notices and plays it with
SendToKodi instead (SPEC "Sending a link" step 5).

## Scope

- Listen on the event port before `Player.Open`; decide playing / failed /
  undecided from events and a 1 s poll of the play time.
- `smart` memory: `~/.local/state/omakodi/youtube-failed` holds the time of
  the last failure; used for 30 min, cleared on success.
- Messages for each outcome.

## Done when

- [ ] Fake scenarios: `Other.playback_failed` → fallback; `Player.OnStop` before play → fallback; picture up but time frozen 12 s → fallback; time moves 3 s → playing, record cleared; no verdict in 30 s → undecided, no fallback.
- [ ] The video already playing doesn't count as the new one (same `file|label` keeps playing while the new one loads).
- [ ] Event port closed → the poll alone still decides.
- [ ] Tests use a fake clock or short timeouts, so the suite stays fast.
