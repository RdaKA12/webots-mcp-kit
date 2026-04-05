from __future__ import annotations

import json
from pathlib import Path

from webots_mcp_kit.monsterborg_calibration import build_calibration_report


def _write_export(
    root: Path,
    *,
    benchmark: str,
    task_variant: str,
    mean_forward_speed: float,
    encoder_distance: float,
    heading_drift: float,
    reacq: int = 0,
    reacq_steps: int = 0,
    task_quality_summary: dict[str, object] | None = None,
) -> None:
    (root / "artifacts").mkdir(parents=True, exist_ok=True)
    (root / "export.json").write_text(json.dumps({"artifact_standard_version": 1}, indent=2), encoding="utf-8")
    (root / "summary.json").write_text(
        json.dumps(
            {
                "benchmark_summary": {
                    "benchmark_name": benchmark,
                    "task_variant": task_variant,
                    "track_variant": task_variant,
                    "line_reacquisition_events": reacq,
                    "max_line_reacquisition_steps": reacq_steps,
                    "task_quality_summary": task_quality_summary or {},
                }
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (root / "artifacts" / "benchmark-last.json").write_text(
        json.dumps(
            {
                "benchmark": benchmark,
                "robot_profile": "monsterborg-4wd",
                "runtime_target": "interactive-webots",
                "task_variant": task_variant,
                "track_variant": task_variant,
                "line_reacquisition_events": reacq,
                "max_line_reacquisition_steps": reacq_steps,
                "task_quality_summary": task_quality_summary or {},
                "extra_metrics": {
                    "mean_forward_speed": mean_forward_speed,
                    "encoder_distance": encoder_distance,
                    "heading_drift": heading_drift,
                    "collision_count": 0,
                    **(task_quality_summary or {}),
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def test_monsterborg_calibration_report_passes_when_deltas_are_small(tmp_path: Path) -> None:
    sim_root = tmp_path / "sim"
    physical_root = tmp_path / "physical"
    _write_export(sim_root, benchmark="line-follower", task_variant="baseline", mean_forward_speed=4.0, encoder_distance=2.1, heading_drift=0.22, reacq=1, reacq_steps=4)
    _write_export(physical_root, benchmark="line-follower", task_variant="baseline", mean_forward_speed=3.7, encoder_distance=2.0, heading_drift=0.2, reacq=1, reacq_steps=4)
    payload = build_calibration_report(sim_export=sim_root, physical_export=physical_root)
    assert payload["pass"] is True
    assert payload["track_variant"] == "baseline"


def test_monsterborg_calibration_report_fails_when_delta_exceeds_budget(tmp_path: Path) -> None:
    sim_root = tmp_path / "sim"
    physical_root = tmp_path / "physical"
    _write_export(sim_root, benchmark="line-follower", task_variant="baseline", mean_forward_speed=4.0, encoder_distance=2.1, heading_drift=0.22, reacq=1, reacq_steps=4)
    _write_export(physical_root, benchmark="line-follower", task_variant="baseline", mean_forward_speed=2.5, encoder_distance=1.2, heading_drift=0.5, reacq=4, reacq_steps=8)
    payload = build_calibration_report(sim_export=sim_root, physical_export=physical_root)
    assert payload["pass"] is False
    assert payload["failures"]


def test_monsterborg_calibration_report_handles_obstacle_and_waypoint_tasks(tmp_path: Path) -> None:
    obstacle_sim = tmp_path / "obstacle-sim"
    obstacle_physical = tmp_path / "obstacle-physical"
    _write_export(
        obstacle_sim,
        benchmark="obstacle-avoidance",
        task_variant="cluttered",
        mean_forward_speed=3.1,
        encoder_distance=1.8,
        heading_drift=0.18,
        task_quality_summary={"min_front_range": 320.0, "stalled_steps": 1, "obstacle_clearance_violations": 0},
    )
    _write_export(
        obstacle_physical,
        benchmark="obstacle-avoidance",
        task_variant="cluttered",
        mean_forward_speed=3.0,
        encoder_distance=1.76,
        heading_drift=0.17,
        task_quality_summary={"min_front_range": 305.0, "stalled_steps": 1, "obstacle_clearance_violations": 0},
    )
    obstacle_payload = build_calibration_report(sim_export=obstacle_sim, physical_export=obstacle_physical)
    assert obstacle_payload["benchmark"] == "obstacle-avoidance"
    assert obstacle_payload["pass"] is True

    waypoint_sim = tmp_path / "waypoint-sim"
    waypoint_physical = tmp_path / "waypoint-physical"
    _write_export(
        waypoint_sim,
        benchmark="waypoint-nav",
        task_variant="offset-start",
        mean_forward_speed=3.8,
        encoder_distance=2.0,
        heading_drift=0.18,
        task_quality_summary={"progress_ratio": 0.94, "distance_to_goal_final": 0.18, "heading_alignment_error": 0.08},
    )
    _write_export(
        waypoint_physical,
        benchmark="waypoint-nav",
        task_variant="offset-start",
        mean_forward_speed=3.0,
        encoder_distance=1.5,
        heading_drift=0.36,
        task_quality_summary={"progress_ratio": 0.61, "distance_to_goal_final": 0.45, "heading_alignment_error": 0.28},
    )
    waypoint_payload = build_calibration_report(sim_export=waypoint_sim, physical_export=waypoint_physical)
    assert waypoint_payload["benchmark"] == "waypoint-nav"
    assert waypoint_payload["pass"] is False
