from __future__ import annotations

import json
from pathlib import Path

from webots_mcp_kit.monsterborg_line_follow import (
    LineFollowMemory,
    PREDICT,
    RECOVER,
    SEARCH,
    TRACK,
    analyze_scan_rows,
    compute_drive_targets,
    update_memory,
)
from webots_mcp_kit.models import bundled_example_root
from webots_mcp_kit.scenario_ops import build_scenario, scenario_doctor, validate_scenario


def test_analyze_scan_rows_detects_visible_line() -> None:
    rows = [
        [10, 12, 18, 35, 190, 220, 180, 32, 18, 12, 10, 8],
        [10, 12, 18, 40, 200, 230, 190, 36, 20, 12, 10, 8],
        [10, 12, 18, 34, 188, 216, 178, 30, 18, 12, 10, 8],
    ]
    profile = analyze_scan_rows(rows)
    assert profile.line_visible is True
    assert profile.confidence > 0.2
    assert profile.signal_strength_mean > 10.0
    assert abs(profile.center_error) < 0.35


def test_line_follow_memory_enters_search_and_recover() -> None:
    memory = LineFollowMemory()
    invisible = analyze_scan_rows([[4.0] * 12, [4.0] * 12, [4.0] * 12])
    for _ in range(4):
        memory = update_memory(memory, invisible)
    assert memory.state_code in {SEARCH, RECOVER}
    for _ in range(8):
        memory = update_memory(memory, invisible)
    assert memory.state_code == RECOVER


def test_compute_drive_targets_changes_with_tracking_state() -> None:
    visible = analyze_scan_rows([[8, 12, 16, 24, 180, 230, 180, 24, 16, 12, 8, 8]] * 3)
    tracking = LineFollowMemory(state_code=TRACK, lost_steps=0, last_center_error=0.0, search_direction=1.0)
    searching = LineFollowMemory(state_code=SEARCH, lost_steps=6, last_center_error=0.2, search_direction=1.0)
    predicting = LineFollowMemory(state_code=PREDICT, lost_steps=2, last_center_error=0.15, search_direction=1.0)

    track_left, track_right = compute_drive_targets(
        tracking,
        visible,
        max_speed=8.0,
        cruise_speed=5.8,
        minimum_cruise=2.6,
        turn_gain=5.6,
        curvature_gain=2.4,
        search_speed=3.2,
        recover_speed=3.8,
    )
    search_left, search_right = compute_drive_targets(
        searching,
        visible,
        max_speed=8.0,
        cruise_speed=5.8,
        minimum_cruise=2.6,
        turn_gain=5.6,
        curvature_gain=2.4,
        search_speed=3.2,
        recover_speed=3.8,
    )
    predict_left, predict_right = compute_drive_targets(
        predicting,
        visible,
        max_speed=8.0,
        cruise_speed=5.8,
        minimum_cruise=2.6,
        turn_gain=5.6,
        curvature_gain=2.4,
        search_speed=3.2,
        recover_speed=3.8,
    )

    assert track_left > 0.0 and track_right > 0.0
    assert search_left != search_right
    assert predict_left != predict_right


def test_monsterborg_line_follow_variant_specs_validate_and_build(tmp_path: Path) -> None:
    examples_root = bundled_example_root()
    variant_specs = [
        examples_root / "monsterborg" / "line-follower" / "variants" / "baseline.webots-kit.scenario.json",
        examples_root / "monsterborg" / "line-follower" / "variants" / "tight-turns.webots-kit.scenario.json",
        examples_root / "monsterborg" / "line-follower" / "variants" / "broken-line-recovery.webots-kit.scenario.json",
        examples_root / "monsterborg" / "line-follower" / "variants" / "low-contrast.webots-kit.scenario.json",
    ]
    for source_spec in variant_specs:
        scenario_dir = tmp_path / source_spec.stem.replace(".webots-kit", "")
        scenario_dir.mkdir(parents=True, exist_ok=True)
        spec_path = scenario_dir / "webots-kit.scenario.json"
        spec_path.write_text(source_spec.read_text(encoding="utf-8"), encoding="utf-8")
        validation = validate_scenario(spec_path)
        assert validation.valid is True, source_spec.name
        doctor = scenario_doctor(spec_path)
        assert doctor["line_follow_readiness"]["ready"] is True, source_spec.name
        generated = build_scenario(spec_path, force=True)
        metadata = json.loads((scenario_dir / "webots-kit.generated.json").read_text(encoding="utf-8"))
        assert generated.robot_profile == "monsterborg-4wd"
        assert metadata["robot_profile"] == "monsterborg-4wd"
