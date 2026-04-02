from __future__ import annotations

import socket
from typing import Any

from .errors import KitError, coerce_error_payload
from .models import SessionManifest
from .protocol import decode_message, encode_message, read_line, request_id
from .session_store import SessionStore


class SessionClient:
    def __init__(self, manifest: SessionManifest):
        self.manifest = manifest

    @classmethod
    def from_session(cls, session_id: str | None = None) -> "SessionClient":
        store = SessionStore()
        manifest = store.load_manifest(session_id) if session_id else store.latest_manifest()
        if manifest is None:
            raise FileNotFoundError("No active or recorded session manifest was found.")
        return cls(manifest)

    def request(self, action: str, params: dict[str, Any] | None = None, timeout: float = 15.0) -> Any:
        payload = {
            "kind": "admin_request",
            "id": request_id(),
            "action": action,
            "params": params or {},
        }
        with socket.create_connection((self.manifest.host, self.manifest.port), timeout=timeout) as sock:
            sock.sendall(encode_message(payload))
            response = decode_message(read_line(sock))
        if not response.get("ok", False):
            error = coerce_error_payload(response.get("error"), fallback_message="Unknown daemon error.")
            raise KitError(
                error["code"],
                error["message"],
                details={"session_id": self.manifest.session_id, **error.get("details", {})},
                retriable=bool(error.get("retriable", False)),
            )
        return response.get("result")
