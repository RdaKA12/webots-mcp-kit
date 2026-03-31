from __future__ import annotations

import json
import socket
import uuid
from typing import Any


def encode_message(payload: dict[str, Any]) -> bytes:
    return (json.dumps(payload) + "\n").encode("utf-8")


def decode_message(raw: bytes) -> dict[str, Any]:
    return json.loads(raw.decode("utf-8"))


def read_line(sock: socket.socket) -> bytes:
    chunks = bytearray()
    while True:
        char = sock.recv(1)
        if not char:
            break
        if char == b"\n":
            break
        chunks.extend(char)
    if not chunks:
        raise ConnectionError("Socket closed before receiving a line.")
    return bytes(chunks)


def request_id() -> str:
    return uuid.uuid4().hex
