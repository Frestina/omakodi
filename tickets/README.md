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
- **Statuses:** `todo`, `in progress`, `done`, `blocked`.
- New work found along the way goes to the backlog or a new ticket, never
  into the current one.
- **Fixtures are fictional.** No real addresses, hostnames or account names in
  the tests, docs or demo. Live checks go in the git-ignored
  `docs/live-checks.local.md`.
- **Nothing is pushed** until the user says so; there is no GitHub remote yet.

Every ticket has the same parts: front matter (`id`, `title`, `milestone`,
`depends_on`), then Goal, Scope, sometimes Not in this ticket, and Done when.

## Milestones and status

### M1 Terminal: every Kodi action works from `omakodi`

| # | Ticket | Depends on | Status |
| --- | --- | --- | --- |
| 001 | [Config and credentials](001-config-and-credentials.md) | | todo |
| 002 | [JSON-RPC client and fake Kodi](002-rpc-client-and-fake-kodi.md) | 001 | todo |
| 003 | [Remote commands and status](003-remote-commands.md) | 002 | todo |
| 004 | [Send a link: play and queue](004-send-a-link.md) | 002 | todo |
| 005 | [YouTube verdict and fallback](005-youtube-fallback.md) | 004 | todo |
| 006 | [Live check from the terminal](006-live-check-terminal.md) | 003, 005 | todo |

### M2 Shell: the remote, the bar and the keys

| # | Ticket | Depends on | Status |
| --- | --- | --- | --- |
| 007 | [Daemon protocol](007-daemon.md) | 003, 005 | todo |
| 008 | [Service and IPC](008-service-and-ipc.md) | 007 | todo |
| 009 | [Bar widget](009-bar-widget.md) | 008 | todo |
| 010 | [Remote panel](010-remote-panel.md) | 008 | todo |
| 011 | [Keybindings and install](011-keybindings-and-install.md) | 010 | todo |
| 012 | [Live check on this machine](012-live-check-shell.md) | 009, 010, 011 | todo |

### M3 First release: someone else can install and trust it

| # | Ticket | Depends on | Status |
| --- | --- | --- | --- |
| 013 | [Demo and screenshot](013-demo-and-screenshot.md) | 012 | todo |
| 014 | [README, security and docs](014-readme-and-docs.md) | 012 | todo |
| 015 | [Release 0.1.0 and listing](015-release-0-1-0.md) | 013, 014 | todo |
