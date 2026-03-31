from __future__ import annotations

from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from .benchmark import run_benchmark
from .client import SessionClient
from .launcher import start_session

mcp = FastMCP("webots-mcp-kit", json_response=True)


def _client(session: str | None) -> SessionClient:
    return SessionClient.from_session(session)


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


@mcp.tool()
def webots_session_stop(session: str | None = None) -> dict[str, Any]:
    return _client(session).request("stop")


@mcp.tool()
def webots_list_robots(session: str | None = None) -> Any:
    return _client(session).request("list_robots")


@mcp.tool()
def webots_list_devices(session: str | None = None) -> Any:
    return _client(session).request("list_devices")


@mcp.tool()
def webots_get_state(session: str | None = None) -> Any:
    return _client(session).request("get_state")


@mcp.tool()
def webots_get_sensors(session: str | None = None) -> Any:
    return _client(session).request("get_sensors")


@mcp.tool()
def webots_capture_camera(session: str | None = None, camera: str | None = None, path: str | None = None) -> Any:
    return _client(session).request("capture_camera", {"camera": camera, "path": path})


@mcp.tool()
def webots_set_motor_velocity(left: float, right: float, duration_steps: int = 1, session: str | None = None) -> Any:
    return _client(session).request(
        "set_motor_velocity",
        {"left": left, "right": right, "duration_steps": duration_steps},
    )


@mcp.tool()
def webots_step(steps: int = 1, session: str | None = None) -> Any:
    return _client(session).request("step", {"steps": steps})


@mcp.tool()
def webots_pause_resume(paused: bool = True, session: str | None = None) -> Any:
    return _client(session).request("pause_resume", {"paused": paused})


@mcp.tool()
def webots_reset(session: str | None = None) -> Any:
    return _client(session).request("reset")


@mcp.tool()
def webots_run_benchmark(
    scenario: str = "line-follower",
    controller: str | None = "example",
    duration_s: float = 20.0,
    output: str | None = None,
) -> dict[str, Any]:
    output_path = Path(output or f"{scenario}-report.json")
    report = run_benchmark(scenario=scenario, controller=controller, output=output_path, duration_s=duration_s)
    return report.to_dict()


def run() -> None:
    mcp.run(transport="stdio")
