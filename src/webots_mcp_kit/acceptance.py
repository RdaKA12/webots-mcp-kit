from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path

from .models import bundled_example_root

HOSTED_SAFE_ACCEPTANCE_PROFILE = "hosted-safe"
FULL_ACCEPTANCE_PROFILE = "full"


@dataclass(frozen=True, slots=True)
class AcceptanceStep:
    name: str
    args: tuple[str, ...]


def build_clean_user_acceptance_steps(workspace: Path, *, profile: str = FULL_ACCEPTANCE_PROFILE) -> list[AcceptanceStep]:
    root = workspace.resolve()
    controller_path = root / "controllers" / "demo_agent.py"
    controller_edit_plan = root / "controllers" / "controller-edit.json"
    project_root = root / "demo-project"
    spec_path = project_root / "scenarios" / "demo-waypoint" / "webots-kit.scenario.json"
    bundle_root = bundled_example_root()
    import_world = bundle_root / "line-follower" / "worlds" / "line_follower_benchmark.wbt"
    import_controller = bundle_root / "line-follower" / "controllers" / "line_follower_agent.py"
    import_project_root = root / "import-project"
    editable_world = root / "editable-world.wbt"
    world_edit_plan = root / "world-edit.json"

    if profile not in {FULL_ACCEPTANCE_PROFILE, HOSTED_SAFE_ACCEPTANCE_PROFILE}:
        raise ValueError(f"Unsupported acceptance profile: {profile}")

    root.mkdir(parents=True, exist_ok=True)
    controller_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(import_world, editable_world)
    controller_edit_plan.write_text(
        json.dumps({"schema_version": 1, "operations": [{"type": "update_control_constants", "constants": {"CRUISE": 180}}]}, indent=2),
        encoding="utf-8",
    )
    world_edit_plan.write_text(
        json.dumps({"schema_version": 1, "operations": [{"type": "set_spawn", "translation": [-0.4, 0.1, 0.0], "rotation_z": 0.5}]}, indent=2),
        encoding="utf-8",
    )

    steps: list[AcceptanceStep] = []
    if profile == FULL_ACCEPTANCE_PROFILE:
        steps.append(AcceptanceStep("doctor", ("doctor", "--json")))

    steps.extend(
        [
        AcceptanceStep("benchmark_list", ("benchmark", "list")),
        AcceptanceStep("controller_scaffold", ("controller", "scaffold", str(controller_path), "--scenario", "line-follower", "--force")),
        AcceptanceStep("controller_validate", ("controller", "validate", str(controller_path), "--scenario", "line-follower")),
        AcceptanceStep("controller_inspect", ("controller", "inspect", str(controller_path), "--scenario", "line-follower")),
        AcceptanceStep("controller_edit", ("controller", "edit", str(controller_path), "--plan", str(controller_edit_plan))),
        AcceptanceStep("project_init", ("project", "init", str(project_root), "--force")),
        AcceptanceStep("scenario_init", ("scenario", "init", str(project_root / "scenarios" / "demo-waypoint"), "--template", "epuck-waypoint", "--force")),
        AcceptanceStep("scenario_enrich", (str(spec_path),)),
        AcceptanceStep("scenario_validate", ("scenario", "validate", str(spec_path))),
        AcceptanceStep("scenario_build", ("scenario", "build", str(spec_path), "--force")),
        AcceptanceStep("scenario_describe", ("scenario", "describe", str(spec_path))),
        AcceptanceStep("scenario_doctor", ("scenario", "doctor", str(spec_path))),
        AcceptanceStep("world_inspect", ("world", "inspect", str(editable_world), "--json")),
        AcceptanceStep("world_validate", ("world", "validate", str(editable_world), "--json")),
        AcceptanceStep("world_edit", ("world", "edit", str(editable_world), "--plan", str(world_edit_plan))),
        AcceptanceStep(
            "project_import",
            ("project", "import", "--world", str(import_world), "--controller", str(import_controller), "--project-root", str(import_project_root)),
        ),
        ]
    )
    return steps
