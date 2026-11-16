---
id: 012
title: Live check on this machine
milestone: M2
depends_on: [009, 010, 011]
---

## Goal

omakodi runs in the real shell against the real Kodi, and the user uses it for
a few days before release.

## Scope

- Link the checkout into `~/.config/omarchy/plugins/io.github.frestina.omakodi`,
  enable, add the bindings.
- Check widget states, the remote, play/queue from the keys, and leaving
  home (Kodi unreachable) and coming back.
- Collect what the user finds; each becomes a ticket or backlog item.

## Checks by hand

Setup, the bar, the remote's display, play/queue, pause, volume, navigation
and stop were checked through IPC on 2026-11-16 (see the git-ignored live
checks). These need a person at the keyboard. Tick them as you go; note
anything odd in `docs/live-checks.local.md` or tell Claude.

**The keys** (copy a video link first for the second and third)

- [ ] `SUPER SHIFT + K` opens the remote; pressing it again closes it.
- [ ] `SUPER SHIFT ALT + K` plays the copied link; a notification says
      "Playing on Kodi".
- [ ] `SUPER SHIFT CTRL + K` queues it; the notification gives the queue length.
- [ ] With text that has no link copied, either key notifies "no link found"
      and nothing happens on the TV.

**Typing in the open remote**

- [ ] It has the keyboard as soon as it opens (arrows work without a click).
- [ ] Arrows, Enter, Backspace (back), `h` (home), `c` `i` `o` (context,
      info, OSD), Space (play/pause), `x` (stop), `f` (fullscreen) do what
      the button would.
- [ ] Holding an arrow moves steadily and stops when you let go (no late
      extra moves).
- [ ] `+` `-` `m` change the soundbar's volume and mute.
- [ ] `p` / `q` play / queue the copied link; with no link copied the remote
      says "no link found".
- [ ] Esc closes it; so do the close button and the bar icon.
- [ ] Clicking another window while it is open works as usual.

**The remote with the mouse**

- [ ] Each button does the same as its key; Play link / Queue link use the
      clipboard.

**The bar**

- [ ] Hovering the icon shows the title and time while something plays.
- [ ] Optional: set `maxTitleLength` (e.g. 30) on the bar widget; the title
      shows beside the icon, cut short. Set it back to 0 after.

**Wrong password** (you edit the file; Claude doesn't touch the password)

- [ ] Change one letter of the password in `~/.config/omakodi/config.json`.
      Within a minute (about 5 seconds while something plays) the icon turns
      the urgent colour and the tooltip says "wrong username or password".
      Change it back; the icon returns to normal the same way, without a
      restart.

**Away from home and back**

- [ ] Off the home network, the icon disappears after about 45 seconds.
- [ ] The remote (`SUPER SHIFT + K`) says "Kodi isn't answering" with the
      fix ("Is Kodi on, and is this computer on the same network?"), and its
      keys do nothing.
- [ ] Back home, the icon comes back by itself.

**Everyday use**

- [ ] A few days of normal use; anything annoying, slow or surprising is
      noted.

## Done when

- [ ] Every SPEC "Shell surfaces" behaviour seen live, recorded in `docs/live-checks.local.md`.
- [ ] The user has used it for some days and their findings are filed.
