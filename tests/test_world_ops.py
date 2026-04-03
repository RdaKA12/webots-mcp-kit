from __future__ import annotations

import json
import shutil
from pathlib import Path

from webots_mcp_kit.world_ops import edit_world, inspect_world, validate_world


def _example_world(name: str) -> Path:
    return Path(__file__).resolve().parents[1] / "examples" / name / "worlds"


def test_inspect_world_reports_targets() -> None:
    payload = inspect_world(_example_world("obstacle-avoidance") / "obstacle_avoidance_benchmark.wbt")
    assert payload["spatial_summary"]["obstacle_count"] >= 1
    assert payload["robots"]
    assert payload["supported_edit_targets"]


def test_validate_world_ready_for_example() -> None:
    payload = validate_world(_example_world("waypoint-nav") / "waypoint_nav_benchmark.wbt")
    assert payload["status"] == "ready"
    assert payload["issues"] == []


def test_edit_world_updates_spawn_and_adds_obstacle(tmp_path: Path) -> None:
    source = _example_world("waypoint-nav") / "waypoint_nav_benchmark.wbt"
    target = tmp_path / source.name
    shutil.copy2(source, target)
    plan_path = tmp_path / "world-edit.json"
    plan_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "operations": [
                    {"type": "set_spawn", "translation": [-0.4, 0.1, 0.0], "rotation_z": 0.5},
                    {"type": "add_obstacle", "name": "obstacle-generated", "position": [0.2, 0.3], "size": [0.1, 0.1, 0.1]},
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    payload = edit_world(target, plan_path=plan_path)
    assert payload["status"] == "ready"
    updated = inspect_world(target)
    assert updated["spatial_summary"]["obstacle_count"] >= 1
    assert any(node["def_name"] == "EPUCK" for node in updated["robots"] if node["def_name"] is not None)
