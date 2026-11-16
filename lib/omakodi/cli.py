"""The omakodi command."""

import argparse
import json
import sys

from . import __version__, config
from .errors import OK, OmakodiError


def cmd_config(args):
    print(json.dumps(config.load().public(), indent=2))
    return OK


def cmd_init(args):
    path = config.write_template()
    print(f"Wrote {path} (mode 600). Set host, username and password.")
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
