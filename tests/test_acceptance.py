from __future__ import annotations

from pathlib import Path

from webots_mcp_kit.acceptance import build_clean_user_acceptance_steps


def test_clean_user_acceptance_steps_cover_expected_flow(tmp_path: Path) -> None:
    steps = build_clean_user_acceptance_steps(tmp_path / "acceptance")
    names = [step.name for step in steps]
    assert names == [
        "doctor",
        "benchmark_list",
        "controller_scaffold",
        "controller_validate",
        "project_init",
        "scenario_init",
        "scenario_validate",
        "scenario_build",
        "scenario_describe",
        "scenario_doctor",
        "project_import",
    ]
    project_import = steps[-1]
    assert "--world" in project_import.args
    assert "--controller" in project_import.args
