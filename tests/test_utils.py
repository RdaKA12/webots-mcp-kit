from __future__ import annotations

import os
import socket
from pathlib import Path

from webots_mcp_kit.utils import atomic_write_text, choose_free_port


def test_choose_free_port_returns_bindable_port() -> None:
    port = choose_free_port()
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", port))


def test_atomic_write_text_retries_transient_permission_error(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / "sample.txt"
    attempts = {"count": 0}
    real_replace = os.replace

    def flaky_replace(src: str | os.PathLike[str], dst: str | os.PathLike[str]) -> None:
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise PermissionError("transient lock")
        real_replace(src, dst)

    monkeypatch.setattr("webots_mcp_kit.utils.os.replace", flaky_replace)
    atomic_write_text(target, "ok", encoding="utf-8")
    assert target.read_text(encoding="utf-8") == "ok"
    assert attempts["count"] == 3
