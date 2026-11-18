# Security

omakodi is a remote control for a Kodi box on your home network. This page
says what it sends where, where your Kodi password lives, and what it never
writes down.

## What omakodi talks to

The Kodi box named in `~/.config/omakodi/config.json`, on three ports, and
YouTube for one thing (below):

| Port | What | Login |
| --- | --- | --- |
| `httpPort` (8080) | Every command: keys, volume, play, queue, typed text, and reading what is playing (JSON-RPC over HTTP) | Kodi's username and password, as HTTP Basic auth |
| `eventPort` (9777, UDP) | Kodi's EventServer, only for **Turn on the soundbar** (`s`): one packet asking Kodi to run its `CECActivateSource`. No login exists on this port: anyone on your network who can reach it can already send Kodi actions, with or without omakodi | none |
| `tcpPort` (9090) | Kodi's notifications: something started or stopped, Kodi asks for text. omakodi only listens here and sends nothing but a keep-alive | none |

When you **queue** a YouTube link, omakodi asks YouTube's public oEmbed
address (`https://www.youtube.com/oembed`, HTTPS, no key, no login) for the
video's title, so the remote's queue can show it; Kodi has no title for a
queued link until it plays. That request carries the video's ID, as the link
you copied does, and nothing about you or your Kodi. Playing a link, or
queueing one from another site, makes no such request.

**Wake Kodi** (`w`, `omakodi wake`) sends a Wake-on-LAN packet, only when
you ask: one UDP broadcast to your local network (`255.255.255.255`, port
9) carrying the box's MAC address, sent three times. Every device on that
network can see it; it holds nothing else.

omakodi makes no other network connections: no updates, no telemetry. The
links you send are passed to Kodi; Kodi's add-ons (YouTube, SendToKodi and
its yt-dlp) then fetch the video from the site themselves.

## Plain HTTP on your network

Kodi's remote control speaks plain HTTP. That is Kodi's design, and omakodi
can't change it:

- **The password crosses the network unencrypted** with every command
  (Basic auth is only base64). Anyone who can watch the traffic on your
  network can read it, and the links and text you send.
- **Port 9090 has no login at all.** Anyone on your network can connect to
  it and control Kodi, with or without omakodi. You turn it on in Kodi with
  *Allow remote control from applications on other systems*. Turning it off
  makes omakodi slower to notice changes and drops the text field, but
  everything else keeps working.
- **What you type into Kodi's on-screen keyboard** through the remote goes
  over the same plain HTTP. Think twice before typing a password for another
  service that way.

So use omakodi on a network you trust (your home network), and give Kodi a
password you don't use anywhere else. Don't expose Kodi's ports to the
internet.

## Where the password lives

- Only in `~/.config/omakodi/config.json`. `omakodi init` creates it with
  mode 600 in a directory with mode 700.
- omakodi refuses to run with a config that holds a password and is readable
  by group or others, and says how to fix it (`chmod 600`).
- It is never passed as a command-line argument, never stored in the
  shell's settings (`shell.json`), and never put in the daemon's output, an
  error message, a notification or a log. `omakodi config` shows the config
  with the password hidden.
- `omarchy plugin remove` leaves the file in place; delete
  `~/.config/omakodi/` yourself if you don't want it kept.

## What is never written down

- The password (above).
- The stream address of what is playing. Kodi's answers can contain one,
  and a stream from a media-server add-on can carry an API key in it, so
  omakodi never asks for it or passes it on.
- The text of a password prompt. When Kodi asks for a password, omakodi
  drops the text Kodi sends with the request; the remote's field shows dots.
- The clipboard. Play and queue read it only when you press their key, keep
  the first `http(s)` link and send only that link to Kodi.

Besides the config, omakodi writes only `~/.local/state/omakodi/`, which
records when the YouTube add-on last failed and when you last stopped a
video through omakodi (a time each, nothing else), the YouTube mode
chosen in Settings (`youtube-mode.json`, with the `host` it is for) and the
titles of the last 200 links you queued (`titles.json`, mode 600, keyed by
a hash of the queued item), the box's MAC address for Wake-on-LAN
(`mac.json`, mode 600, with the `host` it belongs to), whether the box's
volume keys go to the TV (`volume.json`, the same way), and
`~/.cache/omakodi/art/`: the posters and thumbnails of what played (the 30
most recent, mode 600). Those are fetched from Kodi with the login and named
by a hash of their address, so the address itself (which can carry a media
server's API key) isn't stored.

## The plugin itself

Omarchy plugins run as unsandboxed code inside `omarchy-shell`, with your
user's rights. omakodi's shell part starts one program, its own
`bin/omakodi daemon`, with `/usr/bin/python3 -I` (never a `python3` or
`omakodi` found on PATH). The command-line tool also runs `wl-paste` (to read
the clipboard for `--clipboard`) and `notify-send` (for `--notify`). Review
the repository before enabling it.

## Reporting a problem

Please report security problems privately through GitHub: the repository's
**Security** tab → **Report a vulnerability**. Don't open a public issue for
them.
