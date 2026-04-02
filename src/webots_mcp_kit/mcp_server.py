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
    if not isinstance(payload, dict):
        payload = {}
    devices = payload.get("devices")
    if not isinstance(devices, list):
        devices = []
    return {
        "robot": payload.get("robot"),
        "scenario": payload.get("scenario"),
        "devices": devices,
    }


def _normalize_sensor_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        payload = {}
    return {
        "robot": payload.get("robot"),
        "scenario": payload.get("scenario"),
        "state": payload.get("state") if isinstance(payload.get("state"), dict) else {},
        "sensors": payload.get("sensors") if isinstance(payload.get("sensors"), dict) else {},
        "metrics": payload.get("metrics") if isinstance(payload.get("metrics"), dict) else {},
        "actuators": payload.get("actuators") if isinstance(payload.get("actuators"), dict) else {},
        "meta": payload.get("meta") if isinstance(payload.get("meta"), dict) else {},
    }


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
        return manifest.to_dict()
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
        return _client(session).request("get_state")
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
        return _client(session).request("capture_camera", {"camera": camera, "path": path})
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
        return report.to_dict()
    except Exception as exc:
        return _tool_error(exc)


def run() -> None:
    mcp.run(transport="stdio")
