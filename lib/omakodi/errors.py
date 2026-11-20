"""Errors with a fixed wording and exit code (SPEC "Errors")."""

# Exit codes
OK = 0
FAILED = 1
USAGE = 2
CONFIG = 3
UNREACHABLE = 4
AUTH = 5


class OmakodiError(Exception):
    """A failure the user sees.

    ``kind`` is the fixed wording from SPEC ("not reachable"); ``detail`` adds
    the specifics and the fix. Neither may ever contain the Kodi password.
    ``box``: the name of the box it happened with, when known, so the
    message can name it (SPEC "Messages").
    """

    def __init__(self, kind, detail="", code=FAILED, box=None):
        self.kind = kind
        self.detail = detail
        self.code = code
        self.box = box
        super().__init__(str(self))

    def __str__(self):
        return f"{self.kind}: {self.detail}" if self.detail else self.kind

    def __repr__(self):
        return f"OmakodiError({self.kind!r}, code={self.code})"
