from __future__ import annotations

import json
import socket
import time
from typing import Any


class RuntimeSocketClient:
    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(5.0)
        self.sock.connect((host, port))
        self.sock.setblocking(False)
        self._buffer = bytearray()

    def send(self, payload: dict[str, Any]) -> None:
        self.sock.sendall((json.dumps(payload) + "\n").encode("utf-8"))

    def drain(self) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = []
        while True:
            try:
                chunk = self.sock.recv(4096)
                if not chunk:
                    break
                self._buffer.extend(chunk)
            except BlockingIOError:
                break
        while b"\n" in self._buffer:
            raw, _, remainder = self._buffer.partition(b"\n")
            self._buffer = bytearray(remainder)
            if raw:
                messages.append(json.loads(raw.decode("utf-8")))
        return messages

    def close(self) -> None:
        try:
            self.sock.close()
        except OSError:
            pass


def connect_runtime(host: str, port: int, *, role: str, name: str, meta: dict[str, Any] | None = None) -> RuntimeSocketClient:
    retries = 40
    last_error: Exception | None = None
    for _ in range(retries):
        try:
            client = RuntimeSocketClient(host, port)
            client.send(
                {
                    "kind": "runtime_register",
                    "role": role,
                    "name": name,
                    "meta": meta or {},
                }
            )
            return client
        except OSError as exc:
            last_error = exc
            time.sleep(0.25)
    raise RuntimeError(f"Unable to connect runtime client to daemon: {last_error}") from last_error
