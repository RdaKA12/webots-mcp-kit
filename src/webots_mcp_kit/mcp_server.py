from __future__ import annotations

from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from .benchmark import run_benchmark
from .client import SessionClient
from .controller_authoring import edit_controller, inspect_controller
from .controller_scaffold import scaffold_controller
from .controller_validation import validate_controller
from .errors import KitError, error_dict
from .launcher import start_session
from .world_ops import edit_world, inspect_world, validate_world

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


def _normalize_validation_payload(payload: Any) -> dict[str, Any]:
    payload = payload if isinstance(payload, dict) else {}
    normalized = dict(payload)
    normalized["path"] = payload.get("path")
    normalized["valid"] = bool(payload.get("valid", False))
    normalized["status"] = payload.get("status")
    normalized["integration_mode"] = payload.get("integration_mode")
    normalized["errors"] = payload.get("errors") if isinstance(payload.get("errors"), list) else []
    normalized["warnings"] = payload.get("warnings") if isinstance(payload.get("warnings"), list) else []
    normalized["details"] = payload.get("details") if isinstance(payload.get("details"), dict) else {}
    normalized["summary"] = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    normalized["support_tier"] = payload.get("support_tier")
    normalized["next_step"] = payload.get("next_step")
    return normalized


def _normalize_world_inspect_payload(payload: Any) -> dict[str, Any]:
    payload = payload if isinstance(payload, dict) else {}
    normalized = dict(payload)
    normalized["status"] = payload.get("status")
    normalized["world_path"] = payload.get("world_path")
    normalized["header"] = payload.get("header")
    normalized["externproto"] = payload.get("externproto") if isinstance(payload.get("externproto"), list) else []
    normalized["robots"] = payload.get("robots") if isinstance(payload.get("robots"), list) else []
    normalized["target_robot"] = payload.get("target_robot") if isinstance(payload.get("target_robot"), dict) else None
    normalized["def_map"] = payload.get("def_map") if isinstance(payload.get("def_map"), list) else []
    normalized["controller_bindings"] = payload.get("controller_bindings") if isinstance(payload.get("controller_bindings"), list) else []
    normalized["supported_edit_targets"] = payload.get("supported_edit_targets") if isinstance(payload.get("supported_edit_targets"), list) else []
    normalized["spatial_summary"] = payload.get("spatial_summary") if isinstance(payload.get("spatial_summary"), dict) else {}
    normalized["summary"] = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    normalized["scene_node_summary"] = payload.get("scene_node_summary") if isinstance(payload.get("scene_node_summary"), dict) else {}
    normalized["inferred_task_cues"] = payload.get("inferred_task_cues") if isinstance(payload.get("inferred_task_cues"), dict) else {}
    normalized["node_tree"] = payload.get("node_tree") if isinstance(payload.get("node_tree"), list) else []
    normalized["field_inventory"] = payload.get("field_inventory") if isinstance(payload.get("field_inventory"), dict) else {}
    normalized["def_use_map"] = payload.get("def_use_map") if isinstance(payload.get("def_use_map"), dict) else {}
    normalized["editability"] = payload.get("editability") if isinstance(payload.get("editability"), dict) else {}
    normalized["opaque_regions"] = payload.get("opaque_regions") if isinstance(payload.get("opaque_regions"), list) else []
    normalized["preserve_notes"] = payload.get("preserve_notes") if isinstance(payload.get("preserve_notes"), list) else []
    normalized["supported_mutation_modes"] = payload.get("supported_mutation_modes") if isinstance(payload.get("supported_mutation_modes"), dict) else {}
    normalized["support_tier"] = payload.get("support_tier")
    normalized["next_step"] = payload.get("next_step")
    return normalized


def _normalize_world_validate_payload(payload: Any) -> dict[str, Any]:
    payload = payload if isinstance(payload, dict) else {}
    normalized = dict(payload)
    normalized["world_path"] = payload.get("world_path")
    normalized["valid"] = bool(payload.get("valid", False))
    normalized["status"] = payload.get("status")
    normalized["issues"] = payload.get("issues") if isinstance(payload.get("issues"), list) else []
    normalized["warnings"] = payload.get("warnings") if isinstance(payload.get("warnings"), list) else []
    normalized["supported_edit_targets"] = payload.get("supported_edit_targets") if isinstance(payload.get("supported_edit_targets"), list) else []
    normalized["spatial_summary"] = payload.get("spatial_summary") if isinstance(payload.get("spatial_summary"), dict) else {}
    normalized["summary"] = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    normalized["def_use_map"] = payload.get("def_use_map") if isinstance(payload.get("def_use_map"), dict) else {}
    normalized["opaque_regions"] = payload.get("opaque_regions") if isinstance(payload.get("opaque_regions"), list) else []
    normalized["preserve_notes"] = payload.get("preserve_notes") if isinstance(payload.get("preserve_notes"), list) else []
    normalized["support_tier"] = payload.get("support_tier")
    normalized["next_step"] = payload.get("next_step")
    return normalized


def _normalize_world_edit_payload(payload: Any) -> dict[str, Any]:
    payload = payload if isinstance(payload, dict) else {}
    normalized = dict(payload)
    normalized["world_path"] = payload.get("world_path")
    normalized["applied_operations"] = payload.get("applied_operations") if isinstance(payload.get("applied_operations"), list) else []
    normalized["status"] = payload.get("status")
    normalized["issues"] = payload.get("issues") if isinstance(payload.get("issues"), list) else []
    normalized["warnings"] = payload.get("warnings") if isinstance(payload.get("warnings"), list) else []
    normalized["changed_paths"] = payload.get("changed_paths") if isinstance(payload.get("changed_paths"), list) else []
    normalized["summary"] = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    normalized["validation"] = payload.get("validation") if isinstance(payload.get("validation"), dict) else {}
    normalized["supported_edit_targets"] = payload.get("supported_edit_targets") if isinstance(payload.get("supported_edit_targets"), list) else []
    normalized["def_use_map"] = payload.get("def_use_map") if isinstance(payload.get("def_use_map"), dict) else {}
    normalized["opaque_regions"] = payload.get("opaque_regions") if isinstance(payload.get("opaque_regions"), list) else []
    normalized["preserve_notes"] = payload.get("preserve_notes") if isinstance(payload.get("preserve_notes"), list) else []
    normalized["support_tier"] = payload.get("support_tier")
    normalized["next_step"] = payload.get("next_step")
    return normalized


def _normalize_controller_inspect_payload(payload: Any) -> dict[str, Any]:
    payload = payload if isinstance(payload, dict) else {}
    normalized = dict(payload)
    normalized["path"] = payload.get("path")
    normalized["language"] = payload.get("language")
    normalized["scenario"] = payload.get("scenario")
    normalized["integration_mode"] = payload.get("integration_mode")
    normalized["valid_source"] = bool(payload.get("valid_source", False))
    normalized["editable_regions"] = payload.get("editable_regions") if isinstance(payload.get("editable_regions"), list) else []
    normalized["markers_present"] = bool(payload.get("markers_present", False))
    normalized["default_camera"] = payload.get("default_camera")
    normalized["device_bindings"] = payload.get("device_bindings") if isinstance(payload.get("device_bindings"), list) else []
    normalized["device_access_inventory"] = payload.get("device_access_inventory") if isinstance(payload.get("device_access_inventory"), list) else []
    normalized["telemetry_sections"] = payload.get("telemetry_sections") if isinstance(payload.get("telemetry_sections"), dict) else {}
    normalized["telemetry_contract"] = payload.get("telemetry_contract") if isinstance(payload.get("telemetry_contract"), dict) else {}
    normalized["benchmark_readiness"] = payload.get("benchmark_readiness") if isinstance(payload.get("benchmark_readiness"), dict) else {}
    normalized["benchmark_contract_gaps"] = payload.get("benchmark_contract_gaps") if isinstance(payload.get("benchmark_contract_gaps"), list) else []
    normalized["function_inventory"] = payload.get("function_inventory") if isinstance(payload.get("function_inventory"), list) else []
    normalized["editable_symbols"] = payload.get("editable_symbols") if isinstance(payload.get("editable_symbols"), list) else []
    normalized["compile_readiness"] = payload.get("compile_readiness") if isinstance(payload.get("compile_readiness"), dict) else {}
    normalized["runtime_readiness"] = payload.get("runtime_readiness") if isinstance(payload.get("runtime_readiness"), dict) else {}
    normalized["controller_fix_hints"] = payload.get("controller_fix_hints") if isinstance(payload.get("controller_fix_hints"), list) else []
    normalized["issues"] = payload.get("issues") if isinstance(payload.get("issues"), list) else []
    normalized["status"] = payload.get("status")
    normalized["summary"] = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    normalized["support_tier"] = payload.get("support_tier")
    normalized["next_step"] = payload.get("next_step")
    return normalized


def _normalize_controller_scaffold_payload(payload: Any) -> dict[str, Any]:
    payload = payload if isinstance(payload, dict) else {}
    normalized = dict(payload)
    normalized["path"] = payload.get("path")
    normalized["scenario"] = payload.get("scenario")
    normalized["language"] = payload.get("language")
    normalized["default_camera"] = payload.get("default_camera")
    normalized["copied_files"] = payload.get("copied_files") if isinstance(payload.get("copied_files"), list) else []
    normalized["editable_regions"] = payload.get("editable_regions") if isinstance(payload.get("editable_regions"), list) else []
    normalized["source_controller"] = payload.get("source_controller")
    normalized["spec_path"] = payload.get("spec_path")
    normalized["world"] = payload.get("world")
    normalized["target_robot_name"] = payload.get("target_robot_name")
    normalized["target_robot_def"] = payload.get("target_robot_def")
    normalized["support_tier"] = payload.get("support_tier")
    normalized["next_step"] = payload.get("next_step")
    return normalized


def _normalize_controller_edit_payload(payload: Any) -> dict[str, Any]:
    payload = payload if isinstance(payload, dict) else {}
    normalized = dict(payload)
    normalized["path"] = payload.get("path")
    normalized["language"] = payload.get("language")
    normalized["applied_operations"] = payload.get("applied_operations") if isinstance(payload.get("applied_operations"), list) else []
    normalized["editable_regions"] = payload.get("editable_regions") if isinstance(payload.get("editable_regions"), list) else []
    normalized["status"] = payload.get("status")
    normalized["summary"] = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    normalized["benchmark_readiness"] = payload.get("benchmark_readiness") if isinstance(payload.get("benchmark_readiness"), dict) else {}
    normalized["benchmark_contract_gaps"] = payload.get("benchmark_contract_gaps") if isinstance(payload.get("benchmark_contract_gaps"), list) else []
    normalized["controller_fix_hints"] = payload.get("controller_fix_hints") if isinstance(payload.get("controller_fix_hints"), list) else []
    normalized["support_tier"] = payload.get("support_tier")
    normalized["next_step"] = payload.get("next_step")
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


@mcp.tool()
def webots_world_inspect(path: str) -> dict[str, Any]:
    try:
        return _normalize_world_inspect_payload(inspect_world(Path(path)))
    except Exception as exc:
        return _tool_error(exc)


@mcp.tool()
def webots_world_validate(path: str) -> dict[str, Any]:
    try:
        return _normalize_world_validate_payload(validate_world(Path(path)))
    except Exception as exc:
        return _tool_error(exc)


@mcp.tool()
def webots_world_edit(path: str, plan: str) -> dict[str, Any]:
    try:
        return _normalize_world_edit_payload(edit_world(Path(path), plan_path=Path(plan)))
    except Exception as exc:
        return _tool_error(exc)


@mcp.tool()
def webots_controller_inspect(path: str, scenario: str | None = None, spec: str | None = None) -> dict[str, Any]:
    try:
        return _normalize_controller_inspect_payload(
            inspect_controller(Path(path), scenario=scenario, spec_path=Path(spec) if spec else None).to_dict()
        )
    except Exception as exc:
        return _tool_error(exc)


@mcp.tool()
def webots_controller_scaffold(
    path: str,
    scenario: str = "line-follower",
    language: str = "python",
    spec: str | None = None,
    world: str | None = None,
    robot_name: str | None = None,
    robot_def: str | None = None,
) -> dict[str, Any]:
    try:
        return _normalize_controller_scaffold_payload(
            scaffold_controller(
                path=Path(path),
                scenario=scenario,
                language=language,
                spec_path=Path(spec) if spec else None,
                world=Path(world) if world else None,
                robot_name=robot_name,
                robot_def=robot_def,
            )
        )
    except Exception as exc:
        return _tool_error(exc)


@mcp.tool()
def webots_controller_validate(path: str, scenario: str | None = None, strict: bool = False, spec: str | None = None) -> dict[str, Any]:
    try:
        return _normalize_validation_payload(
            validate_controller(Path(path), scenario=scenario, strict=strict, spec_path=Path(spec) if spec else None).to_dict()
        )
    except Exception as exc:
        return _tool_error(exc)


@mcp.tool()
def webots_controller_edit(path: str, plan: str) -> dict[str, Any]:
    try:
        return _normalize_controller_edit_payload(edit_controller(Path(path), plan_path=Path(plan)))
    except Exception as exc:
        return _tool_error(exc)


def run() -> None:
    mcp.run(transport="stdio")
