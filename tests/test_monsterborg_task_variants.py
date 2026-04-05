from __future__ import annotations

from pathlib import Path

from webots_mcp_kit.models import bundled_example_root
from webots_mcp_kit.scenario_ops import build_scenario, scenario_doctor, validate_scenario


def test_monsterborg_obstacle_and_waypoint_variant_specs_validate_and_build(tmp_path: Path) -> None:
    examples_root = bundled_example_root()
    variant_specs = [
        examples_root / "monsterborg" / "obstacle-avoidance" / "variants" / "baseline.webots-kit.scenario.json",
        examples_root / "monsterborg" / "obstacle-avoidance" / "variants" / "narrow-corridor.webots-kit.scenario.json",
        examples_root / "monsterborg" / "waypoint-nav" / "variants" / "baseline.webots-kit.scenario.json",
        examples_root / "monsterborg" / "waypoint-nav" / "variants" / "tight-waypoints.webots-kit.scenario.json",
    ]
    for source_spec in variant_specs:
        scenario_dir = tmp_path / source_spec.stem.replace(".webots-kit", "")
        scenario_dir.mkdir(parents=True, exist_ok=True)
        spec_path = scenario_dir / "webots-kit.scenario.json"
        spec_path.write_text(source_spec.read_text(encoding="utf-8"), encoding="utf-8")
        validation = validate_scenario(spec_path)
        assert validation.valid is True, source_spec.name
        doctor = scenario_doctor(spec_path)
        if "obstacle-avoidance" in source_spec.as_posix():
            assert doctor["obstacle_readiness"]["ready"] is True, source_spec.name
            assert doctor["clearance_layout_readiness"]["ready"] is True, source_spec.name
        else:
            assert doctor["waypoint_readiness"]["ready"] is True, source_spec.name
            assert doctor["goal_alignment_readiness"]["ready"] is True, source_spec.name
        generated = build_scenario(spec_path, force=True)
        assert generated.robot_profile == "monsterborg-4wd"
