from __future__ import annotations

import json
from pathlib import Path

from webots_mcp_kit.errors import KitError
from webots_mcp_kit import mcp_server
from webots_mcp_kit.models import bundled_example_root
from webots_mcp_kit.scenario_ops import init_project, init_scenario


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


def test_world_authoring_payloads_are_stable(tmp_path: Path) -> None:
    examples_root = bundled_example_root()
    source_world = examples_root / "line-follower" / "worlds" / "line_follower_benchmark.wbt"
    editable_world = tmp_path / "editable-world.wbt"
    editable_world.write_text(source_world.read_text(encoding="utf-8"), encoding="utf-8")
    plan_path = tmp_path / "world-edit.json"
    plan_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "operations": [
                    {"type": "add_landmark", "name": "stable-landmark", "position": [0.0, 0.0], "radius": 0.04}
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    inspect_payload = mcp_server.webots_world_inspect(str(editable_world))
    validate_payload = mcp_server.webots_world_validate(str(editable_world))
    edit_payload = mcp_server.webots_world_edit(str(editable_world), str(plan_path))

    assert inspect_payload["status"] == "ready"
    assert isinstance(inspect_payload["externproto"], list)
    assert isinstance(inspect_payload["robots"], list)
    assert isinstance(inspect_payload["supported_edit_targets"], list)
    assert isinstance(inspect_payload["node_tree"], list)
    assert isinstance(inspect_payload["field_inventory"], dict)
    assert isinstance(inspect_payload["editability"], dict)
    assert isinstance(inspect_payload["supported_mutation_modes"], dict)
    assert isinstance(inspect_payload["def_use_map"], dict)
    assert isinstance(inspect_payload["spatial_summary"], dict)
    assert inspect_payload["support_tier"] == "experimental-foundation"

    assert validate_payload["world_path"] == str(editable_world)
    assert isinstance(validate_payload["valid"], bool)
    assert isinstance(validate_payload["issues"], list)
    assert isinstance(validate_payload["warnings"], list)
    assert isinstance(validate_payload["supported_edit_targets"], list)
    assert isinstance(validate_payload["summary"], dict)
    assert isinstance(validate_payload["def_use_map"], dict)
    assert isinstance(validate_payload["opaque_regions"], list)
    assert validate_payload["support_tier"] == "experimental-foundation"

    assert edit_payload["world_path"] == str(editable_world)
    assert isinstance(edit_payload["applied_operations"], list)
    assert isinstance(edit_payload["changed_paths"], list)
    assert isinstance(edit_payload["summary"], dict)
    assert isinstance(edit_payload["validation"], dict)
    assert edit_payload["support_tier"] == "experimental-foundation"


def test_controller_authoring_payloads_are_stable(tmp_path: Path) -> None:
    project_root = tmp_path / "controller-project"
    init_project(project_root)
    scenario_dir = project_root / "scenarios" / "demo-waypoint"
    init_scenario(scenario_dir, template="epuck-waypoint")
    spec_path = scenario_dir / "webots-kit.scenario.json"
    payload = json.loads(spec_path.read_text(encoding="utf-8"))
    payload["layout"]["walls"] = [{"name": "wall-preview", "start": [-0.2, -0.3], "end": [-0.2, 0.3], "thickness": 0.02, "height": 0.08}]
    spec_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    controller_path = tmp_path / "demo_agent.py"
    edit_plan_path = tmp_path / "controller-edit.json"
    edit_plan_path.write_text(
        json.dumps(
                {
                    "schema_version": 1,
                    "operations": [
                        {"type": "inject_helper_function", "code": "def preview_helper() -> float:\n    return 1.0"}
                    ],
                    "scenario_context": {"scenario": "waypoint-nav"},
                },
            indent=2,
        ),
        encoding="utf-8",
    )

    scaffold_payload = mcp_server.webots_controller_scaffold(
        path=str(controller_path),
        scenario="waypoint-nav",
        language="python",
        spec=str(spec_path),
        world=str(scenario_dir / "worlds" / "demo-waypoint.wbt"),
        robot_name="epuck-demo-waypoint-waypoint-nav",
        robot_def="EPUCK",
    )
    inspect_payload = mcp_server.webots_controller_inspect(str(controller_path), scenario="waypoint-nav", spec=str(spec_path))
    validate_payload = mcp_server.webots_controller_validate(str(controller_path), scenario="waypoint-nav", strict=True, spec=str(spec_path))
    edit_payload = mcp_server.webots_controller_edit(str(controller_path), str(edit_plan_path))

    assert scaffold_payload["path"] == str(controller_path)
    assert scaffold_payload["language"] == "python"
    assert isinstance(scaffold_payload["copied_files"], list)
    assert isinstance(scaffold_payload["editable_regions"], list)
    assert scaffold_payload["spec_path"] == str(spec_path)
    assert scaffold_payload["target_robot_def"] == "EPUCK"
    assert scaffold_payload["support_tier"] == "experimental-foundation"

    assert inspect_payload["path"] == str(controller_path)
    assert inspect_payload["language"] == "python"
    assert inspect_payload["status"] in {"ready", "misconfigured"}
    assert isinstance(inspect_payload["editable_regions"], list)
    assert isinstance(inspect_payload["device_bindings"], list)
    assert isinstance(inspect_payload["device_access_inventory"], list)
    assert isinstance(inspect_payload["telemetry_sections"], dict)
    assert isinstance(inspect_payload["telemetry_contract"], dict)
    assert isinstance(inspect_payload["benchmark_readiness"], dict)
    assert isinstance(inspect_payload["benchmark_contract_gaps"], list)
    assert isinstance(inspect_payload["function_inventory"], list)
    assert isinstance(inspect_payload["editable_symbols"], list)
    assert isinstance(inspect_payload["compile_readiness"], dict)
    assert isinstance(inspect_payload["runtime_readiness"], dict)
    assert isinstance(inspect_payload["controller_fix_hints"], list)
    assert isinstance(inspect_payload["issues"], list)
    assert isinstance(inspect_payload["summary"], dict)
    assert inspect_payload["support_tier"] == "experimental-foundation"
    assert isinstance(inspect_payload["next_step"], str)

    assert validate_payload["path"] == str(controller_path)
    assert isinstance(validate_payload["valid"], bool)
    assert validate_payload["status"] in {"ready", "misconfigured"}
    assert isinstance(validate_payload["errors"], list)
    assert isinstance(validate_payload["warnings"], list)
    assert isinstance(validate_payload["details"], dict)
    assert isinstance(validate_payload["summary"], dict)
    assert validate_payload["support_tier"] == "experimental-foundation"
    assert isinstance(validate_payload["next_step"], str)

    assert edit_payload["path"] == str(controller_path)
    assert edit_payload["language"] == "python"
    assert isinstance(edit_payload["applied_operations"], list)
    assert isinstance(edit_payload["editable_regions"], list)
    assert edit_payload["status"] in {"ready", "misconfigured"}
    assert isinstance(edit_payload["summary"], dict)
    assert isinstance(edit_payload["benchmark_readiness"], dict)
    assert isinstance(edit_payload["benchmark_contract_gaps"], list)
    assert isinstance(edit_payload["controller_fix_hints"], list)
    assert edit_payload["support_tier"] == "experimental-foundation"
    assert isinstance(edit_payload["next_step"], str)
