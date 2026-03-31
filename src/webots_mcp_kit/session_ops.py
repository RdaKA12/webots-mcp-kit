from __future__ import annotations

import json
from pathlib import Path

from .launcher import inspect_session, stop_session
from .session_store import SessionStore


def format_session_inspect(payload: dict[str, object]) -> str:
    return json.dumps(payload, indent=2)


def session_log_paths(session_id: str) -> list[dict[str, str | int | bool]]:
    store = SessionStore()
    return store.log_inventory(session_id)


def read_session_log(session_id: str, name: str, tail: int | None = None) -> str:
    store = SessionStore()
    path = store.artifacts_dir(session_id) / name
    if not path.exists():
        raise FileNotFoundError(f"Log file '{name}' was not found for session '{session_id}'.")
    content = path.read_text(encoding="utf-8", errors="replace")
    if tail is None:
        return content
    lines = content.splitlines()
    return "\n".join(lines[-tail:])


def inspect_session_json(session_id: str) -> str:
    return json.dumps(inspect_session(session_id), indent=2)


def stop_session_json(session_id: str) -> str:
    return json.dumps(stop_session(session_id).to_dict(), indent=2)
