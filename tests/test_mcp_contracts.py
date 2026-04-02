from __future__ import annotations

from webots_mcp_kit.errors import KitError
from webots_mcp_kit import mcp_server


def test_list_devices_payload_is_stable() -> None:
    payload = mcp_server._normalize_device_payload({"robot": "epuck", "devices": [{"name": "camera"}]})
    assert payload == {"robot": "epuck", "scenario": None, "devices": [{"name": "camera"}]}


def test_get_sensors_payload_is_stable() -> None:
    payload = mcp_server._normalize_sensor_payload({"robot": "epuck", "metrics": {"center_error": 0.0}})
    assert payload == {
        "robot": "epuck",
        "scenario": None,
        "state": {},
        "sensors": {},
        "metrics": {"center_error": 0.0},
        "actuators": {},
        "meta": {},
    }


def test_get_state_includes_session_state() -> None:
    payload = mcp_server._normalize_state_payload(
        {
            "session": {"session_id": "s1", "status": "ready"},
            "session_state": {"status": "ready", "scenario": "line-follower"},
            "control_paused": False,
            "runtime_summary": {},
            "runtimes": {},
        }
    )
    assert payload["session_state"]["status"] == "ready"


def test_session_start_payload_is_stable() -> None:
    payload = mcp_server._normalize_session_start_payload(
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
    )
    assert payload["session_id"] == "s1"
    assert payload["environment"] == {"python_executable": "python.exe"}
    assert payload["extra"] == "kept"


def test_capture_camera_payload_is_stable() -> None:
    payload = mcp_server._normalize_capture_camera_payload({"path": "capture.ppm", "extra": "kept"})
    assert payload == {"path": "capture.ppm", "width": None, "height": None, "extra": "kept"}


def test_run_benchmark_payload_is_stable() -> None:
    payload = mcp_server._normalize_benchmark_payload(
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
    )
    assert payload["benchmark"] == "waypoint-nav"
    assert payload["extra_metrics"] == {}
    assert payload["extra"] == "kept"


def test_mcp_tool_failure_payload_is_structured() -> None:
    payload = mcp_server._tool_error(KitError("render-init-failed", "Render init failed.", details={"session_id": "s1"}))
    assert payload == {
        "ok": False,
        "error": {
            "code": "render-init-failed",
            "message": "Render init failed.",
            "details": {"session_id": "s1"},
            "retriable": False,
        },
    }
