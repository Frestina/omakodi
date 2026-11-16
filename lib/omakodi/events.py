"""Kodi's push notifications on its TCP JSON-RPC port (SPEC "Talking to Kodi")."""

import codecs
import json
import socket
import time

CONNECT_TIMEOUT = 4.0
IDLE_BEFORE_PING = 30.0
PING_TIMEOUT = 10.0
MAX_MESSAGE = 1024 * 1024
BACKOFF_START = 1.0
BACKOFF_MAX = 10.0


class ConnectionLost(Exception):
    pass


class JsonSplitter:
    """Splits a stream of concatenated JSON objects (Kodi sends no delimiter).

    Counts brace depth outside strings. Text outside an object (whitespace) is
    skipped; an object over MAX_MESSAGE characters is a protocol error.
    """

    def __init__(self):
        self._buf = []
        self._depth = 0
        self._in_string = False
        self._escape = False
        self._size = 0

    def feed(self, text):
        out = []
        for ch in text:
            if self._depth == 0:
                if ch != "{":
                    continue  # whitespace or junk between objects
                self._buf = []
                self._size = 0
            self._buf.append(ch)
            self._size += 1
            if self._size > MAX_MESSAGE:
                raise ConnectionLost("message too large")
            if self._in_string:
                if self._escape:
                    self._escape = False
                elif ch == "\\":
                    self._escape = True
                elif ch == '"':
                    self._in_string = False
            elif ch == '"':
                self._in_string = True
            elif ch == "{":
                self._depth += 1
            elif ch == "}":
                self._depth -= 1
                if self._depth == 0:
                    out.append("".join(self._buf))
                    self._buf = []
        return out


class EventConnection:
    """One connection to the event port. ``poll`` returns notifications."""

    def __init__(self, host, port, connect_timeout=CONNECT_TIMEOUT, clock=time.monotonic,
                 idle_before_ping=IDLE_BEFORE_PING, ping_timeout=PING_TIMEOUT):
        self.host = host
        self.port = port
        self.connect_timeout = connect_timeout
        self.clock = clock
        self.idle_before_ping = idle_before_ping
        self.ping_timeout = ping_timeout
        self.sock = None

    def open(self):
        try:
            self.sock = socket.create_connection((self.host, self.port), timeout=self.connect_timeout)
        except OSError as e:
            raise ConnectionLost(f"can't connect: {e.strerror or e}") from None
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        self._decoder = codecs.getincrementaldecoder("utf-8")("replace")
        self._splitter = JsonSplitter()
        self._last_received = self.clock()
        self._ping_sent = None
        return self

    def close(self):
        if self.sock is not None:
            try:
                self.sock.close()
            finally:
                self.sock = None

    def __enter__(self):
        return self.open()

    def __exit__(self, *exc):
        self.close()

    def poll(self, timeout):
        """Wait up to ``timeout`` seconds; return a list of (method, data).

        Raises ConnectionLost when Kodi closes the connection or stops
        answering pings.
        """
        if self.sock is None:
            raise ConnectionLost("not connected")
        now = self.clock()
        if self._ping_sent is not None and now - self._ping_sent > self.ping_timeout:
            raise ConnectionLost("Kodi stopped answering")
        if self._ping_sent is None and now - self._last_received > self.idle_before_ping:
            try:
                self.sock.sendall(b'{"jsonrpc":"2.0","id":"ping","method":"JSONRPC.Ping"}')
            except OSError:
                raise ConnectionLost("send failed") from None
            self._ping_sent = now
        self.sock.settimeout(max(timeout, 0.001))
        try:
            data = self.sock.recv(65536)
        except (socket.timeout, TimeoutError):
            return []
        except OSError:
            raise ConnectionLost("read failed") from None
        if not data:
            raise ConnectionLost("closed by Kodi")
        self._last_received = self.clock()
        self._ping_sent = None
        events = []
        for raw in self._splitter.feed(self._decoder.decode(data)):
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue
            method = msg.get("method") if isinstance(msg, dict) else None
            if not isinstance(method, str) or not method:
                continue  # a reply (e.g. to our ping), not a notification
            params = msg.get("params")
            data_obj = params.get("data") if isinstance(params, dict) else None
            events.append((method, data_obj if isinstance(data_obj, dict) else None))
        return events


def follow(cfg, should_stop, on_connected=None, poll_timeout=0.5, sleep=time.sleep,
           backoff_start=BACKOFF_START, backoff_max=BACKOFF_MAX):
    """Yield (method, data) forever, reconnecting with backoff.

    ``should_stop()`` is checked between reads. ``on_connected(bool)`` reports
    the connection state.
    """
    backoff = backoff_start
    while not should_stop():
        conn = EventConnection(cfg.host, cfg.tcp_port)
        try:
            conn.open()
            if on_connected:
                on_connected(True)
            backoff = backoff_start
            while not should_stop():
                for event in conn.poll(poll_timeout):
                    yield event
        except ConnectionLost:
            pass
        finally:
            conn.close()
        if on_connected:
            on_connected(False)
        if should_stop():
            return
        sleep(backoff)
        backoff = min(backoff * 2, backoff_max)
