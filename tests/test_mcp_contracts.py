from __future__ import annotations

from typing import Any

from webots_mcp_kit import mcp_server


class DummyClient:
    def __init__(self, responses: dict[str, Any]):
        self.responses = responses

    def request(self, action: str, params: dict[str, Any] | None = None) -> Any:
        return self.responses[action]


def test_list_devices_payload_is_stable(monkeypatch) -> None:
    monkeypatch.setattr(
        mcp_server,
        "_client",
        lambda session: DummyClient({"list_devices": {"robot": "epuck", "devices": [{"name": "camera"}]}}),
    )
    payload = mcp_server.webots_list_devices()
    assert payload == {"robot": "epuck", "scenario": None, "devices": [{"name": "camera"}]}


def test_get_sensors_payload_is_stable(monkeypatch) -> None:
    monkeypatch.setattr(
        mcp_server,
        "_client",
        lambda session: DummyClient({"get_sensors": {"robot": "epuck", "metrics": {"center_error": 0.0}}}),
    )
    payload = mcp_server.webots_get_sensors()
    assert payload == {
        "robot": "epuck",
        "scenario": None,
        "state": {},
        "sensors": {},
        "metrics": {"center_error": 0.0},
        "actuators": {},
        "meta": {},
    }
