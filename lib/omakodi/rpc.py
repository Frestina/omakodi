"""Kodi's JSON-RPC over HTTP (SPEC "Talking to Kodi")."""

import base64
import http.client
import json
import socket
import urllib.parse

from .errors import AUTH, UNREACHABLE, OmakodiError

CONNECT_TIMEOUT = 4.0
READ_TIMEOUT = 10.0
MAX_RESPONSE = 1024 * 1024


class Kodi:
    """A client for one Kodi box. Holds the password; never puts it in errors."""

    def __init__(self, cfg, connect_timeout=CONNECT_TIMEOUT):
        self.cfg = cfg
        self.connect_timeout = connect_timeout
        self._auth = None
        if cfg.has_login:
            token = base64.b64encode(f"{cfg.username}:{cfg.password}".encode()).decode()
            self._auth = "Basic " + token
        self._id = 0

    def __repr__(self):
        return f"Kodi({self.cfg.host}:{self.cfg.http_port})"

    def call(self, method, params=None, read_timeout=READ_TIMEOUT):
        """Run one JSON-RPC method and return its ``result``."""
        self._id += 1
        body = {"jsonrpc": "2.0", "id": self._id, "method": method}
        if params is not None:
            body["params"] = params
        payload = json.dumps(body).encode()
        headers = {"Content-Type": "application/json"}
        if self._auth:
            headers["Authorization"] = self._auth

        conn = http.client.HTTPConnection(self.cfg.host, self.cfg.http_port, timeout=self.connect_timeout)
        try:
            try:
                conn.connect()
            except socket.gaierror:
                raise OmakodiError(
                    "not reachable",
                    f"can't find host {self.cfg.host!r}; use its IP address or a name your network "
                    f"resolves (an ssh alias doesn't count) in {self.cfg.path}", UNREACHABLE) from None
            except OSError:
                raise self._unreachable() from None
            conn.sock.settimeout(read_timeout)
            try:
                conn.request("POST", "/jsonrpc", body=payload, headers=headers)
                resp = conn.getresponse()
                raw = resp.read(MAX_RESPONSE + 1)
            except (socket.timeout, TimeoutError):
                raise OmakodiError("not reachable", f"Kodi didn't answer {method} in time", UNREACHABLE) from None
            except (OSError, http.client.HTTPException):
                raise self._unreachable() from None
        finally:
            conn.close()

        if resp.status == 401:
            raise OmakodiError("wrong username or password",
                               f"Kodi refused the login; check username and password in {self.cfg.path}", AUTH)
        if resp.status != 200:
            raise OmakodiError(f"http {resp.status}", f"from Kodi for {method}")
        if len(raw) > MAX_RESPONSE:
            raise OmakodiError("bad response", f"Kodi's answer to {method} is too large")
        try:
            reply = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise OmakodiError("bad response", f"Kodi's answer to {method} is not JSON") from None
        if not isinstance(reply, dict):
            raise OmakodiError("bad response", f"Kodi's answer to {method} is not JSON-RPC")
        error = reply.get("error")
        if error is not None:
            message = error.get("message") if isinstance(error, dict) else None
            raise KodiCallError(method, str(message or "unknown error")[:200])
        if "result" not in reply:
            raise OmakodiError("bad response", f"Kodi's answer to {method} has no result")
        return reply["result"]

    def image(self, art_url, max_bytes, read_timeout=READ_TIMEOUT):
        """The bytes Kodi's ``/image/`` serves for an ``image://…`` art URL.
        Raises OmakodiError when it isn't there or is larger than ``max_bytes``.
        Errors never name the URL (it can carry a media server's API key)."""
        path = "/image/" + urllib.parse.quote(art_url, safe="")
        headers = {"Authorization": self._auth} if self._auth else {}
        conn = http.client.HTTPConnection(self.cfg.host, self.cfg.http_port, timeout=self.connect_timeout)
        try:
            try:
                conn.connect()
                conn.sock.settimeout(read_timeout)
                conn.request("GET", path, headers=headers)
                resp = conn.getresponse()
                raw = resp.read(max_bytes + 1)
            except (OSError, http.client.HTTPException):
                raise self._unreachable() from None
        finally:
            conn.close()
        if resp.status == 401:
            raise OmakodiError("wrong username or password", "Kodi refused the login for an image", AUTH)
        if resp.status != 200:
            raise OmakodiError(f"http {resp.status}", "from Kodi for an image")
        if len(raw) > max_bytes:
            raise OmakodiError("image too large", f"over {max_bytes} bytes")
        return raw

    def _unreachable(self):
        return OmakodiError("not reachable",
                            f"no answer from {self.cfg.host}:{self.cfg.http_port} (away from home?)", UNREACHABLE)


class KodiCallError(OmakodiError):
    """Kodi answered, with a JSON-RPC error (e.g. a method that failed)."""

    def __init__(self, method, message):
        self.method = method
        self.message = message
        super().__init__("kodi error", f"{message} ({method})")
