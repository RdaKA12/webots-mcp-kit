from __future__ import annotations

from pathlib import Path

from .benchmarks import get_scenario
from .controller_authoring import scaffold_controller_artifacts
from .robot_profiles import robot_profile_from_template


def scaffold_controller(
    *,
    path: Path,
    scenario: str,
    force: bool = False,
    language: str = "python",
    spec_path: Path | None = None,
    world: Path | None = None,
    robot_profile: str | None = None,
    robot_name: str | None = None,
    robot_def: str | None = None,
) -> dict[str, object]:
    effective_robot_profile = robot_profile
    if effective_robot_profile is None and spec_path is not None:
        from .scenario_ops import load_scenario_spec

        spec = load_scenario_spec(spec_path)
        effective_robot_profile = robot_profile_from_template(str(spec.robot.get("template") or "e-puck"))
    scenario_def = get_scenario(scenario, robot_profile=effective_robot_profile)
    payload = scaffold_controller_artifacts(
        path=path,
        scenario=scenario,
        language=language,
        robot_profile=scenario_def.robot_profile,
        force=force,
    )
    payload.update(
        {
            "source_controller": str(scenario_def.controller),
            "spec_path": str(spec_path) if spec_path else None,
            "world": str(world) if world else None,
            "target_robot_name": robot_name or scenario_def.target_robot_name,
            "target_robot_def": robot_def or scenario_def.target_robot_def,
            "robot_family": scenario_def.robot_family,
            "robot_profile": scenario_def.robot_profile,
            "support_tier": "experimental-foundation",
            "next_step": f"Run `webots-kit controller inspect \"{payload['path']}\" --scenario {scenario}` or `webots-kit controller validate \"{payload['path']}\" --strict --json`.",
        }
    )
    return payload
