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
    assert payload["node_tree"]
    assert "defs" in payload["def_use_map"]
    assert "opaque_regions" in payload


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


def test_validate_world_reports_broken_use(tmp_path: Path) -> None:
    world = tmp_path / "broken-use.wbt"
    world.write_text(
        '#VRML_SIM R2025a utf8\n'
        'DEF EPUCK E-puck {\n'
        '  name "broken-bot"\n'
        '  controller "<extern>"\n'
        '  boundingObject USE MISSING_BOX\n'
        '}\n'
        'Robot {\n'
        '  name "kit-supervisor"\n'
        '  controller "<extern>"\n'
        '  supervisor TRUE\n'
        '}\n',
        encoding="utf-8",
    )

    payload = validate_world(world)

    assert payload["status"] == "misconfigured"
    assert any(issue["code"] == "broken-use" for issue in payload["issues"])


def test_edit_world_supports_generic_field_and_top_level_add(tmp_path: Path) -> None:
    source = _example_world("line-follower") / "line_follower_benchmark.wbt"
    target = tmp_path / source.name
    shutil.copy2(source, target)
    plan_path = tmp_path / "generic-world-edit.json"
    plan_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "operations": [
                    {"type": "set_field", "selector": {"by_type": "WorldInfo"}, "field": "title", "value": "Edited Benchmark"},
                    {"type": "add_node", "node_raw": 'Transform {\n  translation 0 0 0\n  children [\n  ]\n}'},
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    payload = edit_world(target, plan_path=plan_path)
    world_text = target.read_text(encoding="utf-8")
    updated = inspect_world(target)

    assert payload["status"] == "ready"
    assert "Edited Benchmark" in world_text
    assert any(node["node_type"] == "Transform" for node in updated["supported_edit_targets"])


def test_edit_world_supports_nested_selector_filters(tmp_path: Path) -> None:
    world = tmp_path / "nested-world.wbt"
    world.write_text(
        '#VRML_SIM R2025a utf8\n'
        'Transform {\n'
        '  children [\n'
        '    Transform {\n'
        '      translation 0 0 0\n'
        '    }\n'
        '  ]\n'
        '}\n'
        'DEF EPUCK E-puck {\n'
        '  name "nested-bot"\n'
        '  controller "<extern>"\n'
        '}\n'
        'Robot {\n'
        '  name "kit-supervisor"\n'
        '  controller "<extern>"\n'
        '  supervisor TRUE\n'
        '}\n',
        encoding="utf-8",
    )
    root_path = inspect_world(world)["supported_edit_targets"][0]["node_path"]
    plan_path = tmp_path / "nested-edit.json"
    plan_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "operations": [
                    {
                        "type": "set_transform",
                        "selector": {"by_parent_path": root_path, "by_child_index": 0, "by_type": "Transform"},
                        "translation": [0.2, 0.0, 0.0],
                    }
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    payload = edit_world(world, plan_path=plan_path)
    updated = inspect_world(world)
    nested = next(node for node in updated["supported_edit_targets"] if node["parent_path"] == root_path and node["child_ordinal"] == 0)

    assert payload["status"] == "ready"
    assert nested["translation"] == [0.2, 0.0, 0.0]


def test_edit_world_supports_clone_node_with_unique_def(tmp_path: Path) -> None:
    source = _example_world("line-follower") / "line_follower_benchmark.wbt"
    target = tmp_path / source.name
    shutil.copy2(source, target)
    plan_path = tmp_path / "clone-edit.json"
    plan_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "operations": [
                    {"type": "clone_node", "selector": {"by_def": "WALL"}}
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    payload = edit_world(target, plan_path=plan_path)
    updated = inspect_world(target)

    assert payload["status"] == "ready"
    assert "WALL_COPY1" in updated["def_map"]


def test_edit_world_supports_move_node_between_parents(tmp_path: Path) -> None:
    world = tmp_path / "move-world.wbt"
    world.write_text(
        '#VRML_SIM R2025a utf8\n'
        'DEF SOURCE Transform {\n'
        '  children [\n'
        '    Solid {\n'
        '      name "crate-a"\n'
        '    }\n'
        '  ]\n'
        '}\n'
        'DEF TARGET Transform {\n'
        '  children [\n'
        '  ]\n'
        '}\n'
        'DEF EPUCK E-puck {\n'
        '  name "move-bot"\n'
        '  controller "<extern>"\n'
        '}\n'
        'Robot {\n'
        '  name "kit-supervisor"\n'
        '  controller "<extern>"\n'
        '  supervisor TRUE\n'
        '}\n',
        encoding="utf-8",
    )
    plan_path = tmp_path / "move-edit.json"
    plan_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "operations": [
                    {
                        "type": "move_node",
                        "selector": {"by_parent_path": "/World/DEF:SOURCE", "by_child_index": 0, "by_type": "Solid"},
                        "parent_selector": {"by_def": "TARGET"},
                    }
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    payload = edit_world(world, plan_path=plan_path)
    updated = inspect_world(world)
    source_children = [node for node in updated["supported_edit_targets"] if node["parent_path"] == "/World/DEF:SOURCE"]
    target_children = [node for node in updated["supported_edit_targets"] if node["parent_path"] == "/World/DEF:TARGET"]

    assert payload["status"] == "ready"
    assert source_children == []
    assert any(node["name"] == "crate-a" for node in target_children)


def test_edit_world_supports_reorder_children(tmp_path: Path) -> None:
    world = tmp_path / "reorder-world.wbt"
    world.write_text(
        '#VRML_SIM R2025a utf8\n'
        'DEF GROUP Transform {\n'
        '  children [\n'
        '    Solid {\n'
        '      name "crate-a"\n'
        '    }\n'
        '    Solid {\n'
        '      name "crate-b"\n'
        '    }\n'
        '  ]\n'
        '}\n'
        'DEF EPUCK E-puck {\n'
        '  name "reorder-bot"\n'
        '  controller "<extern>"\n'
        '}\n'
        'Robot {\n'
        '  name "kit-supervisor"\n'
        '  controller "<extern>"\n'
        '  supervisor TRUE\n'
        '}\n',
        encoding="utf-8",
    )
    plan_path = tmp_path / "reorder-edit.json"
    plan_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "operations": [
                    {
                        "type": "reorder_children",
                        "selector": {"by_def": "GROUP"},
                        "order": ["crate-b", "crate-a"],
                    }
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    payload = edit_world(world, plan_path=plan_path)
    updated = inspect_world(world)
    ordered = sorted(
        [node for node in updated["supported_edit_targets"] if node["parent_path"] == "/World/DEF:GROUP"],
        key=lambda item: item["child_ordinal"],
    )

    assert payload["status"] == "ready"
    assert [node["name"] for node in ordered] == ["crate-b", "crate-a"]


def test_edit_world_supports_replace_geometry_and_appearance(tmp_path: Path) -> None:
    world = tmp_path / "shape-world.wbt"
    world.write_text(
        '#VRML_SIM R2025a utf8\n'
        'Transform {\n'
        '  children [\n'
        '    Shape {\n'
        '      appearance PBRAppearance {\n'
        '        baseColor 0.1 0.1 0.1\n'
        '      }\n'
        '      geometry Box {\n'
        '        size 0.1 0.1 0.1\n'
        '      }\n'
        '    }\n'
        '  ]\n'
        '}\n'
        'DEF EPUCK E-puck {\n'
        '  name "shape-bot"\n'
        '  controller "<extern>"\n'
        '}\n'
        'Robot {\n'
        '  name "kit-supervisor"\n'
        '  controller "<extern>"\n'
        '  supervisor TRUE\n'
        '}\n',
        encoding="utf-8",
    )
    plan_path = tmp_path / "shape-edit.json"
    plan_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "operations": [
                    {"type": "replace_geometry", "selector": {"by_type": "Shape"}, "node_raw": "Sphere {\n  radius 0.15\n}"},
                    {
                        "type": "replace_appearance",
                        "selector": {"by_type": "Shape"},
                        "node_raw": "Appearance {\n  material Material {\n    diffuseColor 1 0 0\n  }\n}",
                    },
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    payload = edit_world(world, plan_path=plan_path)
    updated = inspect_world(world)
    sphere_nodes = [node for node in updated["supported_edit_targets"] if node["node_type"] == "Sphere"]
    appearance_nodes = [node for node in updated["supported_edit_targets"] if node["node_type"] == "Appearance"]

    assert payload["status"] == "ready"
    assert sphere_nodes
    assert appearance_nodes
