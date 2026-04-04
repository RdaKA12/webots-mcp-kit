from __future__ import annotations

import json
from pathlib import Path

from webots_mcp_kit.benchmark import list_benchmarks
from webots_mcp_kit.controller_authoring import inspect_controller
from webots_mcp_kit.controller_scaffold import scaffold_controller
from webots_mcp_kit.controller_validation import validate_controller
from webots_mcp_kit.models import bundled_example_root
from webots_mcp_kit.robot_profiles import get_robot_profile, robot_profile_names, robot_profile_registry
from webots_mcp_kit.scenario_ops import build_scenario, import_project, init_scenario, validate_scenario
from webots_mcp_kit.world_ops import edit_world, validate_world


def test_robot_profile_registry_exposes_epuck_and_monsterborg() -> None:
    registry = robot_profile_registry()
    assert set(robot_profile_names()) == {"e-puck", "monsterborg-4wd"}
    assert registry["e-puck"].robot_family == "e-puck"
    assert registry["monsterborg-4wd"].robot_family == "monsterborg"
    assert registry["monsterborg-4wd"].runtime_targets == ("interactive-webots", "monsterborg-physical")
    assert registry["monsterborg-4wd"].default_templates["line-follow"] == "monsterborg-line-track"


def test_monsterborg_profile_device_contract_is_stable() -> None:
    profile = get_robot_profile("monsterborg-4wd")
    assert profile.drive_model == "4wd-skid-steer"
    assert profile.default_camera == "front_camera"
    assert profile.logical_drive_channels == ("left_drive", "right_drive")
    assert tuple(profile.device_contract["motors"]) == (
        "front_left_motor",
        "rear_left_motor",
        "front_right_motor",
        "rear_right_motor",
    )
    assert tuple(profile.device_contract["encoders"]) == ("left_encoder", "right_encoder")
    assert tuple(profile.device_contract["range"]) == ("front_range",)
    assert tuple(profile.device_contract["imu"]) == ("imu",)


def test_monsterborg_controller_scaffold_and_validation(tmp_path: Path) -> None:
    target = tmp_path / "monsterborg_line_agent.py"
    payload = scaffold_controller(path=target, scenario="line-follower", language="python", robot_profile="monsterborg-4wd")
    assert payload["robot_family"] == "monsterborg"
    assert payload["robot_profile"] == "monsterborg-4wd"
    source = target.read_text(encoding="utf-8")
    assert 'robot.getDevice("front_left_motor")' in source
    assert 'robot.getDevice("rear_left_motor")' in source
    assert 'robot.getDevice("front_right_motor")' in source
    assert 'robot.getDevice("rear_right_motor")' in source
    assert 'robot.getDevice("front_camera")' in source
    inspection = inspect_controller(target, scenario="line-follower", robot_profile="monsterborg-4wd")
    assert inspection.robot_family == "monsterborg"
    assert inspection.robot_profile == "monsterborg-4wd"
    result = validate_controller(target, scenario="line-follower", strict=True, robot_profile="monsterborg-4wd")
    assert result.valid is True
    assert result.details["robot_family"] == "monsterborg"
    assert result.details["robot_profile"] == "monsterborg-4wd"


def test_monsterborg_scenario_build_and_import_are_robot_aware(tmp_path: Path) -> None:
    scenario_dir = tmp_path / "monsterborg-waypoint"
    init_payload = init_scenario(scenario_dir, template="monsterborg-waypoint")
    assert init_payload["template"] == "monsterborg-waypoint"

    spec_path = scenario_dir / "webots-kit.scenario.json"
    validation = validate_scenario(spec_path)
    assert validation.valid is True

    built = build_scenario(spec_path, force=True)
    assert built.robot_family == "monsterborg"
    assert built.robot_profile == "monsterborg-4wd"
    assert built.runtime_target == "interactive-webots"

    generated_metadata = json.loads((scenario_dir / "webots-kit.generated.json").read_text(encoding="utf-8"))
    assert generated_metadata["robot_family"] == "monsterborg"
    assert generated_metadata["robot_profile"] == "monsterborg-4wd"
    assert generated_metadata["runtime_target"] == "interactive-webots"

    imported = import_project(world=Path(built.world_path), controller=Path(built.controller_path), project_root=tmp_path / "imported")
    assert imported["discovered_robot_family"] == "monsterborg"
    assert imported["suggested_robot_profile"] == "monsterborg-4wd"
    assert imported["runtime_target"] == "interactive-webots"
    assert imported["physical_adapter_supported"] is True
    assert imported["controller_authoring_context"]["robot_family"] == "monsterborg"
    assert imported["controller_authoring_context"]["robot_profile"] == "monsterborg-4wd"


def test_list_benchmarks_includes_monsterborg_rows() -> None:
    rows = list_benchmarks()
    assert any(row["name"] == "line-follower" and row["robot_profile"] == "e-puck" for row in rows)
    assert any(row["name"] == "line-follower" and row["robot_profile"] == "monsterborg-4wd" for row in rows)
    assert any(row["name"] == "waypoint-nav" and row["robot_family"] == "monsterborg" for row in rows)


def test_monsterborg_import_prefers_line_follow_for_line_world(tmp_path: Path) -> None:
    examples_root = bundled_example_root()
    world = examples_root / "monsterborg" / "line-follower" / "worlds" / "monsterborg_line_follower_benchmark.wbt"
    controller = examples_root / "monsterborg" / "line-follower" / "controllers" / "monsterborg_line_follower_agent.py"
    imported = import_project(world=world, controller=controller, project_root=tmp_path / "imported")
    assert imported["inferred_scenario_kind"] == "line-follow"
    assert imported["suggested_benchmark_name"] == "line-follower"
    assert imported["suggested_robot_profile"] == "monsterborg-4wd"


def test_monsterborg_world_edit_set_spawn_defaults_to_target_robot(tmp_path: Path) -> None:
    examples_root = bundled_example_root()
    source_world = examples_root / "monsterborg" / "line-follower" / "worlds" / "monsterborg_line_follower_benchmark.wbt"
    editable_world = tmp_path / "monsterborg_editable.wbt"
    editable_world.write_text(source_world.read_text(encoding="utf-8"), encoding="utf-8")
    plan = tmp_path / "world-edit.json"
    plan.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "operations": [{"type": "set_spawn", "translation": [-1.0, 0.12, 0.0], "rotation_z": 0.1}],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    payload = edit_world(editable_world, plan_path=plan)
    assert payload["status"] == "ready"
    assert validate_world(editable_world)["valid"] is True
