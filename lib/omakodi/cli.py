"""The omakodi command."""

import argparse
import json
import sys

from . import __version__, config, desktop, shortcuts, wol
from .youtubemode import youtube_mode
from .control import ACTIONS, Controller, parse_position
from .eventserver import SOUNDBAR_SENT
from .state import StopNote
from .nowplaying import now_playing
from .rpc import Kodi
from .share import make_sender
from .errors import OK, OmakodiError


def cmd_config(args):
    cfg = config.load()
    shown = cfg.public()
    mode, source = youtube_mode(cfg)
    shown["youtubeMode"] = mode
    shown["youtubeModeFrom"] = "chosen in the remote" if source == "remote" else "config file"
    print(json.dumps(shown, indent=2))
    return OK


def cmd_init(args):
    path = config.write_template()
    print(f"Wrote {path} (mode 600). Set host, username and password.")
    return OK


def cmd_control(args):
    Controller(Kodi(config.load()), stops=StopNote()).run(args.action)
    if args.action == "soundbaron":
        print(SOUNDBAR_SENT + ".")
    return OK


def cmd_seek(args):
    seconds = parse_position(args.position)
    if seconds is None:
        raise OmakodiError("bad position", "seconds, MM:SS or H:MM:SS", 2)
    Controller(Kodi(config.load())).seek(seconds)
    return OK


def cmd_volume(args):
    Controller(Kodi(config.load())).set_volume(args.level)
    return OK


def cmd_audio(args):
    Controller(Kodi(config.load())).audio(args.index)
    return OK


def cmd_shortcut(args):
    if not 1 <= args.button <= shortcuts.SLOTS:
        raise OmakodiError("usage", f"BUTTON is 1 to {shortcuts.SLOTS}", 2)
    cfg = config.load()
    method, params = shortcuts.open_call(shortcuts.ShortcutStore().buttons(cfg.host)[args.button - 1][0])
    Kodi(cfg).call(method, params)
    return OK


def cmd_wake(args):
    mac = wol.wake(config.load(), wol.MacStore())
    print(f"{wol.SENT} ({mac}).")
    return OK


def cmd_status(args):
    print(json.dumps(now_playing(Kodi(config.load())), ensure_ascii=False))
    return OK


def cmd_send(args):
    def report(message, error=False):
        print(message, file=sys.stderr if error else sys.stdout, flush=True)
        if args.notify:
            desktop.notify(message, error)

    try:
        if args.clipboard:
            if args.text:
                raise OmakodiError("usage", "give a link or --clipboard, not both", 2)
            text = desktop.read_clipboard()
        else:
            text = " ".join(args.text)
        sender = make_sender(config.load())
        send = sender.queue if args.command == "queue" else sender.play
        report(send(text, progress=report))
    except OmakodiError as e:
        report(f"omakodi: {e}", error=True)
        return e.code
    return OK


def cmd_daemon(args):
    from . import daemon
    daemon.main()  # does not return


def build_parser():
    p = argparse.ArgumentParser(
        prog="omakodi",
        description="A keyboard remote for Kodi.",
    )
    p.add_argument("--version", action="version", version=f"omakodi {__version__}")
    sub = p.add_subparsers(dest="command", metavar="COMMAND", required=True)

    s = sub.add_parser("config", help="check the config and show it, without the password")
    s.set_defaults(func=cmd_config)
    s = sub.add_parser("init", help="write a config template (mode 600) if there is none")
    s.set_defaults(func=cmd_init)
    s = sub.add_parser("control", help="send a remote action")
    s.add_argument("action", choices=ACTIONS, metavar="ACTION", help=", ".join(ACTIONS))
    s.set_defaults(func=cmd_control)
    s = sub.add_parser("seek", help="jump to a position in what is playing")
    s.add_argument("position", metavar="POSITION", help="seconds, MM:SS or H:MM:SS from the start")
    s.set_defaults(func=cmd_seek)
    s = sub.add_parser("audio", help="play another audio track of what is playing")
    s.add_argument("index", type=int, metavar="INDEX", help="the track's index, as `omakodi status` lists it")
    s.set_defaults(func=cmd_audio)
    for name, what in (("play", "play a link now"), ("queue", "queue a link (plays it if nothing is playing)")):
        s = sub.add_parser(name, help=what)
        s.add_argument("text", nargs="*", help="a link, or text containing one")
        s.add_argument("--clipboard", action="store_true", help="take the link from the clipboard")
        s.add_argument("--notify", action="store_true", help="also show the result as a notification")
        s.set_defaults(func=cmd_send)
    s = sub.add_parser("volume", help="set Kodi's own volume (not the TV's or soundbar's)")
    s.add_argument("level", type=int, metavar="LEVEL", help="0 to 100")
    s.set_defaults(func=cmd_volume)
    s = sub.add_parser("shortcut", help="open one of the remote's shortcut buttons on Kodi")
    s.add_argument("button", type=int, metavar="BUTTON", help="1 to 5, from the left")
    s.set_defaults(func=cmd_shortcut)
    s = sub.add_parser("wake", help="turn the Kodi box on with Wake-on-LAN")
    s.set_defaults(func=cmd_wake)
    s = sub.add_parser("status", help="print what Kodi is playing, as JSON")
    s.set_defaults(func=cmd_status)
    s = sub.add_parser("daemon", help="serve the shell: JSON lines on stdin and stdout")
    s.set_defaults(func=cmd_daemon)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except OmakodiError as e:
        print(f"omakodi: {e}", file=sys.stderr)
        return e.code
    except KeyboardInterrupt:
        return 130
