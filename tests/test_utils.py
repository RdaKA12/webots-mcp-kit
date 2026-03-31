from __future__ import annotations

import socket

from webots_mcp_kit.utils import choose_free_port


def test_choose_free_port_returns_bindable_port() -> None:
    port = choose_free_port()
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", port))
