"""The omakodi command."""

import argparse
import json
import sys

from . import __version__, config, desktop
from .control import ACTIONS, Controller
from .nowplaying import now_playing
from .rpc import Kodi
from .share import Sender
from .state import YoutubeHealth
from .verdict import Verdict
from .errors import OK, OmakodiError


def cmd_config(args):
    print(json.dumps(config.load().public(), indent=2))
    return OK


def cmd_init(args):
    path = config.write_template()
    print(f"Wrote {path} (mode 600). Set host, username and password.")
    return OK


def cmd_control(args):
    Controller(Kodi(config.load())).run(args.action)
    return OK


def cmd_status(args):
    print(json.dumps(now_playing(Kodi(config.load())), ensure_ascii=False))
    return OK


def make_sender(cfg):
    return Sender(Kodi(cfg), cfg.youtube_mode, YoutubeHealth(), verdict=Verdict())


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
    for name, what in (("play", "play a link now"), ("queue", "queue a link (plays it if nothing is playing)")):
        s = sub.add_parser(name, help=what)
        s.add_argument("text", nargs="*", help="a link, or text containing one")
        s.add_argument("--clipboard", action="store_true", help="take the link from the clipboard")
        s.add_argument("--notify", action="store_true", help="also show the result as a notification")
        s.set_defaults(func=cmd_send)
    s = sub.add_parser("status", help="print what Kodi is playing, as JSON")
    s.set_defaults(func=cmd_status)
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
