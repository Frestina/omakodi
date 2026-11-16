"""A fake Kodi for tests and the demo: JSON-RPC over HTTP and the TCP event port.

All data is fictional. It binds to 127.0.0.1 only.
"""

import base64
import json
import os
import socket
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "lib"))

from omakodi.config import Config  # noqa: E402


class FakeKodi:
    def __init__(self, username="kodi", password="fake-password"):
        self.username = username
        self.password = password
        self.results = {}  # method -> result, or callable(params) -> result
        self.errors = {}  # method -> message (JSON-RPC error)
        self.http_status = None  # force a status for every request
        self.raw_reply = None  # force a raw body for every request
        self.delay = 0.0  # seconds before answering
        self.calls = []  # (method, params)
        self.auth_headers = []
        self._lock = threading.Lock()
        self._event_clients = []
        self._accept_events = True
        self.answer_pings = True
        self.pings = 0

    # ---- lifecycle -------------------------------------------------------------

    def start(self):
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                fake._handle_http(self)

        self.http = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.http.daemon_threads = True
        threading.Thread(target=self.http.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True).start()

        self.tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.tcp.bind(("127.0.0.1", 0))
        self.tcp.listen(8)
        threading.Thread(target=self._accept_loop, daemon=True).start()
        return self

    def stop(self):
        self.http.shutdown()
        self.http.server_close()
        self._accept_events = False
        try:
            self.tcp.close()
        except OSError:
            pass
        self.drop_event_clients()

    @property
    def http_port(self):
        return self.http.server_address[1]

    @property
    def tcp_port(self):
        return self.tcp.getsockname()[1]

    def config(self, path="(fake)", **overrides):
        values = dict(host="127.0.0.1", http_port=self.http_port, tcp_port=self.tcp_port,
                      username=self.username, password=self.password)
        values.update(overrides)
        return Config(path, **values)

    def config_json(self):
        return {"host": "127.0.0.1", "httpPort": self.http_port, "tcpPort": self.tcp_port,
                "username": self.username, "password": self.password}

    # ---- HTTP ------------------------------------------------------------------

    def _handle_http(self, req):
        length = int(req.headers.get("Content-Length") or 0)
        body = req.rfile.read(length)
        auth = req.headers.get("Authorization")
        with self._lock:
            self.auth_headers.append(auth)
        if self.delay:
            time.sleep(self.delay)
        if self.http_status:
            return self._reply(req, self.http_status, b"")
        if self.username or self.password:
            expected = "Basic " + base64.b64encode(f"{self.username}:{self.password}".encode()).decode()
            if auth != expected:
                return self._reply(req, 401, b"")
        if self.raw_reply is not None:
            return self._reply(req, 200, self.raw_reply)
        msg = json.loads(body)
        method, params = msg.get("method"), msg.get("params")
        with self._lock:
            self.calls.append((method, params))
        if method in self.errors:
            out = {"jsonrpc": "2.0", "id": msg.get("id"),
                   "error": {"code": -32100, "message": self.errors[method]}}
        else:
            result = self.results.get(method, "OK")
            if callable(result):
                result = result(params)
            out = {"jsonrpc": "2.0", "id": msg.get("id"), "result": result}
        self._reply(req, 200, json.dumps(out).encode())

    @staticmethod
    def _reply(req, status, body):
        req.send_response(status)
        req.send_header("Content-Type", "application/json")
        req.send_header("Content-Length", str(len(body)))
        req.end_headers()
        try:
            req.wfile.write(body)
        except OSError:
            pass  # the client gave up (timeout tests)

    def methods(self):
        with self._lock:
            return [m for m, _ in self.calls]

    def clear_calls(self):
        with self._lock:
            self.calls.clear()

    # ---- TCP events ------------------------------------------------------------

    def _accept_loop(self):
        while self._accept_events:
            try:
                client, _ = self.tcp.accept()
            except OSError:
                return
            with self._lock:
                self._event_clients.append(client)
            threading.Thread(target=self._client_loop, args=(client,), daemon=True).start()

    def _client_loop(self, client):
        while True:
            try:
                data = client.recv(65536)
            except OSError:
                return
            if not data:
                return
            if b"JSONRPC.Ping" in data:
                with self._lock:
                    self.pings += 1
                if self.answer_pings:
                    self._send(client, b'{"id":"ping","jsonrpc":"2.0","result":"pong"}')

    def _send(self, client, raw):
        try:
            client.sendall(raw)
        except OSError:
            pass

    def event_clients(self):
        with self._lock:
            return len(self._event_clients)

    def wait_for_event_client(self, count=1, timeout=5):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if self.event_clients() >= count:
                return True
            time.sleep(0.01)
        return False

    def push(self, method, data=None):
        msg = {"jsonrpc": "2.0", "method": method, "params": {"data": data, "sender": "xbmc"}}
        self.push_raw(json.dumps(msg).encode())

    def push_raw(self, raw):
        with self._lock:
            clients = list(self._event_clients)
        for c in clients:
            self._send(c, raw)

    def drop_event_clients(self):
        with self._lock:
            clients, self._event_clients = self._event_clients, []
        for c in clients:
            try:
                c.shutdown(socket.SHUT_RDWR)
                c.close()
            except OSError:
                pass


def unused_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


# ---- `python3 -I tests/fakekodi.py serve DIR`: a standing fake for live checks --
#
# Writes DIR/config.json (an omakodi config pointing at the fake, no login)
# and plays the scene in DIR/scene.json, re-read when it changes:
#   {"state": "idle" | "playing" | "paused", "title": "…", "subtitle": "…",
#    "positionSec": 393, "durationSec": 3009, "delaySec": 0.5}
# delaySec (0-5) makes every answer slow, like a busy Kodi.
# A change pushes the matching player event, so the daemon updates at once.
# While "playing", the position advances in real time. Fictional data only.

SCENE_EVENTS = {"idle": "Player.OnStop", "playing": "Player.OnPlay", "paused": "Player.OnPause"}


class Scene:
    def __init__(self, path):
        self.path = path
        self.key = None
        self.data = {"state": "idle"}
        self.position = 0.0
        self.since = time.monotonic()
        self.lock = threading.Lock()

    def reload(self):
        try:
            st = os.stat(self.path)
            key = (st.st_mtime_ns, st.st_size)
        except OSError:
            key = None
        if key == self.key:
            return None
        self.key = key
        try:
            with open(self.path) as f:
                data = json.load(f)
        except (OSError, ValueError):
            data = {"state": "idle"}
        if not isinstance(data, dict) or data.get("state") not in SCENE_EVENTS:
            data = {"state": "idle"}
        with self.lock:
            self.data = data
            self.position = float(data.get("positionSec", 0))
            self.since = time.monotonic()
        return data["state"]

    def now(self):
        with self.lock:
            data = dict(self.data)
            pos = self.position
            if data["state"] == "playing":
                pos += time.monotonic() - self.since
        return data, int(pos)


def _hms(seconds):
    return {"hours": seconds // 3600, "minutes": seconds // 60 % 60, "seconds": seconds % 60, "milliseconds": 0}


def serve(directory):
    os.makedirs(directory, mode=0o700, exist_ok=True)
    scene = Scene(os.path.join(directory, "scene.json"))
    scene.reload()
    fake = FakeKodi(username="", password="")
    fake.results["Application.GetProperties"] = {"volume": 64, "muted": False}
    fake.results["Addons.GetAddonDetails"] = {"addon": {"enabled": True}}
    fake.results["Playlist.GetProperties"] = {"size": 2}
    fake.results["XBMC.GetInfoBooleans"] = {"Window.IsActive(fullscreenvideo)": False,
                                            "Window.IsActive(videoosd)": False,
                                            "System.HasActiveModalDialog": False}
    fake.results["Player.GetActivePlayers"] = lambda p: (
        [] if scene.now()[0]["state"] == "idle" else [{"playerid": 1, "type": "video"}])
    fake.results["Player.GetItem"] = lambda p: {"item": {
        "type": "movie", "label": str(scene.now()[0].get("title", "")),
        "title": str(scene.now()[0].get("title", "")), "showtitle": str(scene.now()[0].get("subtitle", ""))}}
    fake.results["Player.GetProperties"] = lambda p: {
        "time": _hms(scene.now()[1]), "totaltime": _hms(int(scene.now()[0].get("durationSec", 0))),
        "speed": 1 if scene.now()[0]["state"] == "playing" else 0}
    fake.start()
    cfg = os.path.join(directory, "config.json")
    fd = os.open(cfg + ".tmp", os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump({"host": "127.0.0.1", "httpPort": fake.http_port, "tcpPort": fake.tcp_port}, f)
    os.replace(cfg + ".tmp", cfg)
    print(f"fake Kodi on 127.0.0.1:{fake.http_port}/{fake.tcp_port}; config {cfg}", flush=True)
    # DIR/calls.log: one line per call that changes something (reads such as
    # Player.GetProperties are left out), for checking what a key sent.
    quiet = ("Application.GetProperties", "Player.GetActivePlayers", "Player.GetItem",
             "Player.GetProperties", "XBMC.GetInfoBooleans", "Addons.GetAddonDetails",
             "Playlist.GetProperties", "JSONRPC.Ping")
    logged = 0
    log = open(os.path.join(directory, "calls.log"), "a", buffering=1)
    try:
        while True:
            with fake._lock:
                new_calls, logged = fake.calls[logged:], len(fake.calls)
            for method, params in new_calls:
                if method not in quiet:
                    log.write(json.dumps([method, params]) + "\n")
            changed = scene.reload()
            delay = scene.now()[0].get("delaySec", 0)
            fake.delay = float(delay) if isinstance(delay, (int, float)) and 0 <= delay <= 5 else 0.0
            if changed:
                fake.push(SCENE_EVENTS[changed], {"item": {"type": "movie"}, "player": {"playerid": 1}})
            time.sleep(0.2)
    except KeyboardInterrupt:
        pass
    finally:
        log.close()
        fake.stop()


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] != "serve":
        sys.exit("usage: fakekodi.py serve DIR")
    serve(sys.argv[2])
