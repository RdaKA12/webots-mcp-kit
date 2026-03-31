from __future__ import annotations

from webots_mcp_kit.protocol import decode_message, encode_message


def test_protocol_roundtrip() -> None:
    payload = {"kind": "ping", "value": 3}
    encoded = encode_message(payload)
    assert encoded.endswith(b"\n")
    decoded = decode_message(encoded.rstrip(b"\n"))
    assert decoded == payload
