from __future__ import annotations

from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from .benchmark import run_benchmark
from .client import SessionClient
from .errors import KitError, error_dict
from .launcher import start_session

mcp = FastMCP("webots-mcp-kit", json_response=True)


def _client(session: str | None) -> SessionClient:
    return SessionClient.from_session(session)


def _normalize_device_payload(payload: Any) -> dict[str, Any]:
    payload = payload if isinstance(payload, dict) else {}
    devices = payload.get("devices")
    if not isinstance(devices, list):
        devices = []
    normalized = dict(payload)
    normalized["robot"] = payload.get("robot")
    normalized["scenario"] = payload.get("scenario")
    normalized["devices"] = devices
    return normalized


def _normalize_sensor_payload(payload: Any) -> dict[str, Any]:
    payload = payload if isinstance(payload, dict) else {}
    normalized = dict(payload)
    normalized["robot"] = payload.get("robot")
    normalized["scenario"] = payload.get("scenario")
    normalized["state"] = payload.get("state") if isinstance(payload.get("state"), dict) else {}
    normalized["sensors"] = payload.get("sensors") if isinstance(payload.get("sensors"), dict) else {}
    normalized["metrics"] = payload.get("metrics") if isinstance(payload.get("metrics"), dict) else {}
    normalized["actuators"] = payload.get("actuators") if isinstance(payload.get("actuators"), dict) else {}
    normalized["meta"] = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
    return normalized


def _normalize_session_start_payload(payload: Any) -> dict[str, Any]:
    payload = payload if isinstance(payload, dict) else {}
    normalized = dict(payload)
    normalized["session_id"] = payload.get("session_id")
    normalized["status"] = payload.get("status")
    normalized["scenario"] = payload.get("scenario")
    normalized["target_robot_name"] = payload.get("target_robot_name")
    normalized["target_robot_def"] = payload.get("target_robot_def")
    normalized["host"] = payload.get("host")
    normalized["port"] = payload.get("port")
    normalized["environment"] = payload.get("environment") if isinstance(payload.get("environment"), dict) else {}
    return normalized


def _normalize_state_payload(payload: Any) -> dict[str, Any]:
    payload = payload if isinstance(payload, dict) else {}
    normalized = dict(payload)
    normalized["session"] = payload.get("session") if isinstance(payload.get("session"), dict) else {}
    normalized["session_state"] = payload.get("session_state") if isinstance(payload.get("session_state"), dict) else {}
    normalized["control_paused"] = bool(payload.get("control_paused", False))
    normalized["runtime_summary"] = payload.get("runtime_summary") if isinstance(payload.get("runtime_summary"), dict) else {}
    normalized["runtimes"] = payload.get("runtimes") if isinstance(payload.get("runtimes"), dict) else {}
    return normalized


def _normalize_capture_camera_payload(payload: Any) -> dict[str, Any]:
    payload = payload if isinstance(payload, dict) else {}
    normalized = dict(payload)
    normalized["path"] = payload.get("path")
    normalized["width"] = payload.get("width")
    normalized["height"] = payload.get("height")
    return normalized


def _normalize_benchmark_payload(payload: Any) -> dict[str, Any]:
    payload = payload if isinstance(payload, dict) else {}
    normalized = dict(payload)
    normalized["benchmark"] = payload.get("benchmark")
    normalized["world"] = payload.get("world")
    normalized["controller"] = payload.get("controller")
    normalized["session_mode"] = payload.get("session_mode")
    normalized["sim_time_s"] = payload.get("sim_time_s")
    normalized["steps"] = payload.get("steps")
    normalized["line_loss_events"] = payload.get("line_loss_events")
    normalized["max_line_loss_streak"] = payload.get("max_line_loss_streak")
    normalized["mean_center_error"] = payload.get("mean_center_error")
    normalized["ir_balance_error"] = payload.get("ir_balance_error")
    normalized["pass"] = bool(payload.get("pass", False))
    normalized["artifacts"] = payload.get("artifacts") if isinstance(payload.get("artifacts"), dict) else {}
    normalized["notes"] = payload.get("notes") if isinstance(payload.get("notes"), list) else []
    normalized["extra_metrics"] = payload.get("extra_metrics") if isinstance(payload.get("extra_metrics"), dict) else {}
    return normalized


def _tool_error(exc: Exception) -> dict[str, Any]:
    if isinstance(exc, KitError):
        return {"ok": False, "error": exc.to_dict()}
    return {"ok": False, "error": error_dict("mcp-tool-failed", str(exc))}


@mcp.tool()
def webots_session_start(
    scenario: str = "line-follower",
    world: str | None = None,
    controller: str | None = "example",
    robot_name: str | None = None,
    robot_def: str | None = None,
    mode: str = "fast",
    render: bool = False,
) -> dict[str, Any]:
    try:
        manifest = start_session(
            world=world,
            controller=controller,
            mode=mode,
            render=render,
            scenario=scenario,
            robot_name=robot_name,
            robot_def=robot_def,
        )
        return _normalize_session_start_payload(manifest.to_dict())
    except Exception as exc:
        return _tool_error(exc)


@mcp.tool()
def webots_session_stop(session: str | None = None) -> dict[str, Any]:
    try:
        return _client(session).request("stop")
    except Exception as exc:
        return _tool_error(exc)


@mcp.tool()
def webots_list_robots(session: str | None = None) -> Any:
    try:
        return _client(session).request("list_robots")
    except Exception as exc:
        return _tool_error(exc)


@mcp.tool()
def webots_list_devices(session: str | None = None) -> Any:
    try:
        return _normalize_device_payload(_client(session).request("list_devices"))
    except Exception as exc:
        return _tool_error(exc)


@mcp.tool()
def webots_get_state(session: str | None = None) -> Any:
    try:
        return _normalize_state_payload(_client(session).request("get_state"))
    except Exception as exc:
        return _tool_error(exc)


@mcp.tool()
def webots_get_sensors(session: str | None = None) -> Any:
    try:
        return _normalize_sensor_payload(_client(session).request("get_sensors"))
    except Exception as exc:
        return _tool_error(exc)


@mcp.tool()
def webots_capture_camera(session: str | None = None, camera: str | None = None, path: str | None = None) -> Any:
    try:
        return _normalize_capture_camera_payload(_client(session).request("capture_camera", {"camera": camera, "path": path}))
    except Exception as exc:
        return _tool_error(exc)


@mcp.tool()
def webots_set_motor_velocity(left: float, right: float, duration_steps: int = 1, session: str | None = None) -> Any:
    try:
        return _client(session).request(
            "set_motor_velocity",
            {"left": left, "right": right, "duration_steps": duration_steps},
        )
    except Exception as exc:
        return _tool_error(exc)


@mcp.tool()
def webots_step(steps: int = 1, session: str | None = None) -> Any:
    try:
        return _client(session).request("step", {"steps": steps})
    except Exception as exc:
        return _tool_error(exc)


@mcp.tool()
def webots_pause_resume(paused: bool = True, session: str | None = None) -> Any:
    try:
        return _client(session).request("pause_resume", {"paused": paused})
    except Exception as exc:
        return _tool_error(exc)


@mcp.tool()
def webots_reset(session: str | None = None) -> Any:
    try:
        return _client(session).request("reset")
    except Exception as exc:
        return _tool_error(exc)


@mcp.tool()
def webots_run_benchmark(
    scenario: str = "line-follower",
    controller: str | None = "example",
    duration_s: float = 20.0,
    output: str | None = None,
) -> dict[str, Any]:
    try:
        output_path = Path(output or f"{scenario}-report.json")
        report = run_benchmark(scenario=scenario, controller=controller, output=output_path, duration_s=duration_s)
        return _normalize_benchmark_payload(report.to_dict())
    except Exception as exc:
        return _tool_error(exc)


def run() -> None:
    mcp.run(transport="stdio")
