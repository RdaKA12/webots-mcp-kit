from __future__ import annotations

from typing import Any

from webots_mcp_kit.errors import KitError
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


def test_get_state_includes_session_state(monkeypatch) -> None:
    monkeypatch.setattr(
        mcp_server,
        "_client",
        lambda session: DummyClient(
            {
                "get_state": {
                    "session": {"session_id": "s1", "status": "ready"},
                    "session_state": {"status": "ready", "scenario": "line-follower"},
                    "control_paused": False,
                    "runtime_summary": {},
                    "runtimes": {},
                }
            }
        ),
    )
    payload = mcp_server.webots_get_state()
    assert payload["session_state"]["status"] == "ready"


def test_mcp_tool_failure_payload_is_structured(monkeypatch) -> None:
    monkeypatch.setattr(
        mcp_server,
        "_client",
        lambda session: (_ for _ in ()).throw(KitError("render-init-failed", "Render init failed.", details={"session_id": "s1"})),
    )
    payload = mcp_server.webots_get_state()
    assert payload == {
        "ok": False,
        "error": {
            "code": "render-init-failed",
            "message": "Render init failed.",
            "details": {"session_id": "s1"},
            "retriable": False,
        },
    }
