from __future__ import annotations

from pathlib import Path

from webots_mcp_kit.acceptance import FULL_ACCEPTANCE_PROFILE, HOSTED_SAFE_ACCEPTANCE_PROFILE, build_clean_user_acceptance_steps


def test_clean_user_acceptance_steps_cover_expected_flow(tmp_path: Path) -> None:
    steps = build_clean_user_acceptance_steps(tmp_path / "acceptance", profile=FULL_ACCEPTANCE_PROFILE)
    names = [step.name for step in steps]
    assert names == [
        "doctor",
        "benchmark_list",
        "controller_scaffold",
        "controller_validate",
        "controller_inspect",
        "controller_edit",
        "project_init",
        "scenario_init",
        "scenario_enrich",
        "scenario_validate",
        "scenario_build",
        "scenario_describe",
        "scenario_doctor",
        "world_inspect",
        "world_validate",
        "world_edit",
        "mcp_authoring_smoke",
        "project_import",
    ]
    project_import = steps[-1]
    controller_scaffold = next(step for step in steps if step.name == "controller_scaffold")
    project_init = next(step for step in steps if step.name == "project_init")
    scenario_init = next(step for step in steps if step.name == "scenario_init")
    scenario_build = next(step for step in steps if step.name == "scenario_build")
    assert "--force" in controller_scaffold.args
    assert "--force" in project_init.args
    assert "--force" in scenario_init.args
    assert "--force" in scenario_build.args
    assert "--world" in project_import.args
    assert "--controller" in project_import.args


def test_hosted_safe_acceptance_skips_doctor(tmp_path: Path) -> None:
    steps = build_clean_user_acceptance_steps(tmp_path / "acceptance", profile=HOSTED_SAFE_ACCEPTANCE_PROFILE)
    names = [step.name for step in steps]
    assert "doctor" not in names
    assert names[0] == "benchmark_list"
