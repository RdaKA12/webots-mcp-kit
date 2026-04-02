from __future__ import annotations

from typing import Any

from webots_mcp_kit.errors import KitError
from webots_mcp_kit import mcp_server


class DummyClient:
    def __init__(self, responses: dict[str, Any]):
        self.responses = responses

    def request(self, action: str, params: dict[str, Any] | None = None) -> Any:
        return self.responses[action]


class DummyManifest:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def to_dict(self) -> dict[str, Any]:
        return dict(self.payload)


class DummyReport:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def to_dict(self) -> dict[str, Any]:
        return dict(self.payload)


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


def test_session_start_payload_is_stable(monkeypatch) -> None:
    monkeypatch.setattr(
        mcp_server,
        "start_session",
        lambda **kwargs: DummyManifest(
            {
                "session_id": "s1",
                "status": "ready",
                "scenario": "line-follower",
                "target_robot_name": "epuck-line-follower",
                "target_robot_def": "EPUCK",
                "host": "127.0.0.1",
                "port": 55123,
                "environment": {"python_executable": "python.exe"},
                "extra": "kept",
            }
        ),
    )
    payload = mcp_server.webots_session_start()
    assert payload["session_id"] == "s1"
    assert payload["environment"] == {"python_executable": "python.exe"}
    assert payload["extra"] == "kept"


def test_capture_camera_payload_is_stable(monkeypatch) -> None:
    monkeypatch.setattr(
        mcp_server,
        "_client",
        lambda session: DummyClient({"capture_camera": {"path": "capture.ppm", "extra": "kept"}}),
    )
    payload = mcp_server.webots_capture_camera()
    assert payload == {"path": "capture.ppm", "width": None, "height": None, "extra": "kept"}


def test_run_benchmark_payload_is_stable(monkeypatch) -> None:
    monkeypatch.setattr(
        mcp_server,
        "run_benchmark",
        lambda **kwargs: DummyReport(
            {
                "benchmark": "waypoint-nav",
                "world": "world.wbt",
                "controller": "controller.py",
                "session_mode": "fast",
                "sim_time_s": 5.0,
                "steps": 20,
                "line_loss_events": 0,
                "max_line_loss_streak": 0,
                "mean_center_error": 0.0,
                "ir_balance_error": 0.0,
                "pass": True,
                "artifacts": {"stdout": "stdout.log"},
                "notes": ["completed"],
                "extra": "kept",
            }
        ),
    )
    payload = mcp_server.webots_run_benchmark()
    assert payload["benchmark"] == "waypoint-nav"
    assert payload["extra_metrics"] == {}
    assert payload["extra"] == "kept"


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
