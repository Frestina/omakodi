"""The YouTube mode chosen in the remote's Settings, per box (SPEC
"Configuration and credentials"): kept in ~/.local/state/omakodi/
youtube-mode.json and read by every omakodi process, so the play
keybindings follow the remote. Until one is chosen, the config file's.
"""

from .config import YOUTUBE_MODES
from .state import HostValue


def mode_store(directory=None):
    return HostValue("youtube-mode", "mode", YOUTUBE_MODES, directory)


def youtube_mode(cfg, store=None):
    """(mode, "remote" or "config"): what the remote chose for this box, else the config file's."""
    chosen = (store or mode_store()).read(cfg.host)
    if chosen is not None:
        return chosen, "remote"
    return cfg.youtube_mode, "config"
