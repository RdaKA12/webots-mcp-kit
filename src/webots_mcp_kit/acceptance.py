from __future__ import annotations

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
    project_root = root / "demo-project"
    spec_path = project_root / "scenarios" / "demo-waypoint" / "webots-kit.scenario.json"
    bundle_root = bundled_example_root()
    import_world = bundle_root / "line-follower" / "worlds" / "line_follower_benchmark.wbt"
    import_controller = bundle_root / "line-follower" / "controllers" / "line_follower_agent.py"
    import_project_root = root / "import-project"

    if profile not in {FULL_ACCEPTANCE_PROFILE, HOSTED_SAFE_ACCEPTANCE_PROFILE}:
        raise ValueError(f"Unsupported acceptance profile: {profile}")

    steps: list[AcceptanceStep] = []
    if profile == FULL_ACCEPTANCE_PROFILE:
        steps.append(AcceptanceStep("doctor", ("doctor", "--json")))

    steps.extend(
        [
        AcceptanceStep("benchmark_list", ("benchmark", "list")),
        AcceptanceStep("controller_scaffold", ("controller", "scaffold", str(controller_path), "--scenario", "line-follower")),
        AcceptanceStep("controller_validate", ("controller", "validate", str(controller_path), "--scenario", "line-follower")),
        AcceptanceStep("project_init", ("project", "init", str(project_root))),
        AcceptanceStep("scenario_init", ("scenario", "init", str(project_root / "scenarios" / "demo-waypoint"), "--template", "epuck-waypoint")),
        AcceptanceStep("scenario_validate", ("scenario", "validate", str(spec_path))),
        AcceptanceStep("scenario_build", ("scenario", "build", str(spec_path))),
        AcceptanceStep("scenario_describe", ("scenario", "describe", str(spec_path))),
        AcceptanceStep("scenario_doctor", ("scenario", "doctor", str(spec_path))),
        AcceptanceStep(
            "project_import",
            ("project", "import", "--world", str(import_world), "--controller", str(import_controller), "--project-root", str(import_project_root)),
        ),
        ]
    )
    return steps
