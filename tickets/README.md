# Tickets

The work to release omakodi v1, one file per ticket. [SPEC.md](../SPEC.md) is
the source of truth; each ticket names the sections it builds. Later features
(v2, v3) and ideas are in [BACKLOG.md](BACKLOG.md).

## How this works

- **Status lives only in the tables below.** Ticket files hold no status.
- **Next ticket:** the lowest-numbered `todo` whose dependencies are all `done`.
- **Starting:** set it to `in progress`. **Finishing:** every box under "Done
  when" ticked, `tests/run` passes, set it to `done`.
- **Commits** start with the ticket number: `004: route YouTube links`.
- **Statuses:** `todo`, `in progress`, `waiting for check`, `done`, `blocked`.
  `waiting for check`: built, tests pass, committed; only the user's live
  check is left (listed in the git-ignored `docs/live-checks.local.md`
  under "Waiting for the user"). For picking the next ticket it counts as
  done, so work can go on while the user is away; the ticket becomes
  `done` after the user's check.
- New work found along the way goes to the backlog or a new ticket, never
  into the current one.
- **Fixtures are fictional.** No real addresses, hostnames or account names in
  the tests, docs or demo. Live checks go in the git-ignored
  `docs/live-checks.local.md`.
- **Nothing is pushed** until the user says so (public repo: github.com/Frestina/omakodi).

Every ticket has the same parts: front matter (`id`, `title`, `milestone`,
`depends_on`), then Goal, Scope, sometimes Not in this ticket, and Done when.

## Milestones and status

### M1 Terminal: every Kodi action works from `omakodi`

| # | Ticket | Depends on | Status |
| --- | --- | --- | --- |
| 001 | [Config and credentials](001-config-and-credentials.md) | | done |
| 002 | [JSON-RPC client and fake Kodi](002-rpc-client-and-fake-kodi.md) | 001 | done |
| 003 | [Remote commands and status](003-remote-commands.md) | 002 | done |
| 004 | [Send a link: play and queue](004-send-a-link.md) | 002 | done |
| 005 | [YouTube verdict and fallback](005-youtube-fallback.md) | 004 | done |
| 006 | [Live check from the terminal](006-live-check-terminal.md) | 003, 005 | done |

### M2 Shell: the remote, the bar and the keys

| # | Ticket | Depends on | Status |
| --- | --- | --- | --- |
| 007 | [Daemon protocol](007-daemon.md) | 003, 005 | done |
| 008 | [Service and IPC](008-service-and-ipc.md) | 007 | done |
| 009 | [Bar widget](009-bar-widget.md) | 008 | done |
| 010 | [Remote panel](010-remote-panel.md) | 008 | done |
| 011 | [Keybindings and install](011-keybindings-and-install.md) | 010 | done |
| 012 | [Live check on this machine](012-live-check-shell.md) | 009, 010, 011 | done |
| 016 | [IPC play and queue reject text without a link](016-ipc-link-check.md) | 008 | done |
| 017 | [A held arrow skips once during a video](017-held-arrows-in-video.md) | 007, 010 | done |
| 018 | [The remote keeps the keyboard; a click outside closes it](018-remote-keeps-keyboard.md) | 010 | done |
| 019 | [Type into Kodi's keyboard from the remote](019-type-into-kodi.md) | 007, 008, 010, 018 | done |
| 020 | [Next and previous in the queue](020-next-and-previous.md) | 007, 008, 010 | done |
| 021 | [Play keeps the queue](021-play-keeps-the-queue.md) | 004, 005, 020 | done |

### M3 First release: someone else can install and trust it

| # | Ticket | Depends on | Status |
| --- | --- | --- | --- |
| 013 | [Demo and screenshot](013-demo-and-screenshot.md) | 012, 017, 018, 019 | done |
| 014 | [README, security and docs](014-readme-and-docs.md) | 012, 017, 018, 019 | done |
| 015 | [Release 0.1.0 on GitHub](015-release-0-1-0.md) | 013, 014 | done |

### M5 v2: the complete remote

The user's picks from the v2 backlog (2026-11-18). Now playing and the queue
grow the remote itself; no second panel.

| # | Ticket | Depends on | Status |
| --- | --- | --- | --- |
| 023 | [Now playing: seek bar, end time, rewind and fast-forward](023-now-playing-seek.md) | 010, 020 | done |
| 024 | [Artwork in the remote](024-artwork.md) | 023 | done |
| 025 | [The queue in the remote](025-queue-in-the-remote.md) | 021, 023 | done |
| 026 | [Details card](026-details-card.md) | 023, 024 | done |
| 027 | [Audio track picker and player info](027-audio-track-and-info.md) | 023 | done |
| 028 | [Power menu](028-power-menu.md) | 010 | done |
| 029 | [Wake-on-LAN](029-wake-on-lan.md) | 028 | done |
| 030 | [Turn on the soundbar over HDMI-CEC](030-cec-power-on.md) | 028 | done |
| 031 | [TV volume and Kodi volume](031-tv-and-kodi-volume.md) | 023 | done |
| 032 | [Titles for queued links](032-titles-for-queued-links.md) | 025 | done |
| 033 | [Pick the audio track from a list](033-audio-track-list.md) | 027 | done |
| 034 | [Audio tracks say their language](034-audio-track-languages.md) | 033 | done |
| 035 | [The remote's layout, keys grouped by what they do](035-remote-layout.md) | 023, 025, 026, 033 | done |
| 036 | [The header shows the whole fix when Kodi isn't answering](036-header-error-lines.md) | 029, 035 | done |
| 037 | [Release 0.2.0 on GitHub](037-release-0-2-0.md) | 023–036 | done |

### M6 v3: more than one box, shortcuts, and fewer surprises with links

The user's picks from the backlog (2026-11-18).

| # | Ticket | Depends on | Status |
| --- | --- | --- | --- |
| 038 | [Report SendToKodi failures](038-sendtokodi-failures.md) | 004, 005 | done |
| 039 | [A stop you send isn't a YouTube failure](039-stop-is-not-a-failure.md) | 005 | done |
| 040 | [Choose the YouTube mode in the remote's Settings](040-youtube-mode-setting.md) | 005, 010 | done |
| 041 | [Shortcut buttons: the strip of five](041-shortcut-buttons.md) | 035 | done |
| 042 | [Several Kodi boxes, and managing them](042-several-kodi-boxes.md) | 007, 008 | done |

### M7 The same as the phone remote

The user wants omakodi's experience to match their phone remote in every
way (2026-11-18). omakodi's extras stay: the Soundbar row, removing queue
entries, the SendToKodi report (038), a stop that isn't a failure (039),
Reboot and Shut down only when Kodi allows them. Tickets 041 and 042 were
widened the same day.

| # | Ticket | Depends on | Status |
| --- | --- | --- | --- |
| 043 | [Top bar and power menu like the phone remote](043-top-bar-and-power-menu.md) | 028, 029, 030, 040 | done |
| 044 | [The remote's keys like the phone remote](044-remote-keys-like-the-phone.md) | 031, 035, 019 | done |
| 045 | [Now playing like the phone remote](045-now-playing-like-the-phone.md) | 023, 024, 025, 026, 035 | done |
| 046 | [Details like the phone remote](046-details-like-the-phone.md) | 026, 034, 045 | waiting for check |
| 047 | [Kodi's keyboard like the phone remote](047-kodi-keyboard-like-the-phone.md) | 019, 044 | todo |
| 048 | [Messages like the phone remote](048-messages-like-the-phone.md) | 043 | todo |

### M4 Listing: in the marketplace once the remote is complete

| # | Ticket | Depends on | Status |
| --- | --- | --- | --- |
| 022 | [Marketplace listing](022-marketplace-listing.md) | 015, 023–035, the user's go-ahead | blocked |
