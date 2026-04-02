from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from webots_mcp_kit import mcp_server
from webots_mcp_kit.models import bundled_example_root


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", required=True, help="Workspace root used for MCP authoring smoke artifacts.")
    parser.add_argument("--print-only", action="store_true", help="Print the planned actions without executing them.")
    return parser.parse_args(argv)


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def require_success(name: str, payload: dict[str, object]) -> dict[str, object]:
    if payload.get("ok") is False:
        raise RuntimeError(f"{name} failed: {payload}")
    return payload


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    workspace = Path(args.workspace).resolve()
    bundle_root = bundled_example_root()
    source_world = bundle_root / "line-follower" / "worlds" / "line_follower_benchmark.wbt"
    controller_path = workspace / "controllers" / "mcp_demo_agent.py"
    controller_plan = workspace / "controllers" / "controller-edit.json"
    editable_world = workspace / "worlds" / "editable_line_follower.wbt"
    world_plan = workspace / "worlds" / "world-edit.json"

    planned_steps = [
        f"webots_controller_scaffold {controller_path}",
        f"webots_controller_inspect {controller_path}",
        f"webots_controller_validate {controller_path}",
        f"webots_controller_edit {controller_path}",
        f"webots_world_inspect {editable_world}",
        f"webots_world_validate {editable_world}",
        f"webots_world_edit {editable_world}",
    ]
    for step in planned_steps:
        print(f"[mcp-authoring] {step}")
    if args.print_only:
        return 0

    workspace.mkdir(parents=True, exist_ok=True)
    controller_path.parent.mkdir(parents=True, exist_ok=True)
    editable_world.parent.mkdir(parents=True, exist_ok=True)
    if controller_path.exists():
        controller_path.unlink()
    shutil.copy2(source_world, editable_world)
    write_json(
        controller_plan,
        {"schema_version": 1, "operations": [{"type": "inject_helper_function", "code": "def preview_helper() -> float:\n    return 1.0"}]},
    )
    write_json(world_plan, {"schema_version": 1, "operations": [{"type": "add_landmark", "name": "mcp-landmark", "position": [0.0, 0.0], "radius": 0.04}]})

    scaffold_payload = require_success(
        "webots_controller_scaffold",
        mcp_server.webots_controller_scaffold(path=str(controller_path), scenario="line-follower", language="python"),
    )
    inspect_payload = require_success(
        "webots_controller_inspect",
        mcp_server.webots_controller_inspect(path=str(controller_path), scenario="line-follower"),
    )
    validate_payload = require_success(
        "webots_controller_validate",
        mcp_server.webots_controller_validate(path=str(controller_path), scenario="line-follower", strict=False),
    )
    edit_payload = require_success(
        "webots_controller_edit",
        mcp_server.webots_controller_edit(path=str(controller_path), plan=str(controller_plan)),
    )
    world_inspect_payload = require_success(
        "webots_world_inspect",
        mcp_server.webots_world_inspect(path=str(editable_world)),
    )
    world_validate_payload = require_success(
        "webots_world_validate",
        mcp_server.webots_world_validate(path=str(editable_world)),
    )
    world_edit_payload = require_success(
        "webots_world_edit",
        mcp_server.webots_world_edit(path=str(editable_world), plan=str(world_plan)),
    )

    assert scaffold_payload["language"] == "python"
    assert inspect_payload["language"] == "python"
    assert validate_payload["valid"] is True
    assert "inject_helper_function" in edit_payload["applied_operations"]
    assert world_inspect_payload["status"] == "ready"
    assert world_validate_payload["valid"] is True
    assert world_edit_payload["status"] == "ready"

    print(
        json.dumps(
            {
                "controller_path": str(controller_path),
                "world_path": str(editable_world),
                "controller_language": inspect_payload["language"],
                "controller_valid": validate_payload["valid"],
                "world_status": world_inspect_payload["status"],
                "world_valid": world_validate_payload["valid"],
                "world_edit_operations": world_edit_payload["applied_operations"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
