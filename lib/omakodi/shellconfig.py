"""The bar widget's settings in Omarchy's shell.json (SPEC "Configuration
and credentials"): read by every omakodi process, the play keybindings'
included, which run outside the shell.
"""

import json
import os

from .config import YOUTUBE_MODES

PLUGIN_ID = "io.github.frestina.omakodi"
MAX_BYTES = 1024 * 1024
MAX_DEPTH = 20


def shell_json_path():
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    return os.path.join(base, "omarchy", "shell.json")


def _find_entry(node, depth=0):
    """The first object with omakodi's id, searched rather than addressed,
    so a change to where Omarchy keeps the bar layout still finds it."""
    if depth > MAX_DEPTH:
        return None
    if isinstance(node, dict):
        if node.get("id") == PLUGIN_ID:
            return node
        children = node.values()
    elif isinstance(node, list):
        children = node
    else:
        return None
    for child in children:
        found = _find_entry(child, depth + 1)
        if found is not None:
            return found
    return None


def widget_settings(path=None):
    """The bar widget's entry as a dict; {} when it can't be read."""
    path = path or shell_json_path()
    try:
        with open(path, "rb") as f:
            raw = f.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            return {}
        entry = _find_entry(json.loads(raw.decode("utf-8")))
    except (OSError, UnicodeDecodeError, ValueError, RecursionError):
        return {}
    return entry if isinstance(entry, dict) else {}


def youtube_mode(cfg, path=None):
    """(mode, where it came from): the widget's setting, else the config's."""
    mode = widget_settings(path).get("youtubeMode")
    if isinstance(mode, str) and mode in YOUTUBE_MODES:
        return mode, "bar widget settings"
    return cfg.youtube_mode, "config file"
