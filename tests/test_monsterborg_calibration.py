from __future__ import annotations

import json
from pathlib import Path

from webots_mcp_kit.monsterborg_calibration import build_calibration_report


def _write_export(root: Path, *, mean_forward_speed: float, encoder_distance: float, heading_drift: float, reacq: int, reacq_steps: int) -> None:
    (root / "artifacts").mkdir(parents=True, exist_ok=True)
    (root / "export.json").write_text(json.dumps({"artifact_standard_version": 1}, indent=2), encoding="utf-8")
    (root / "summary.json").write_text(
        json.dumps(
            {
                "benchmark_summary": {
                    "benchmark_name": "line-follower",
                    "track_variant": "baseline",
                    "line_reacquisition_events": reacq,
                    "max_line_reacquisition_steps": reacq_steps,
                }
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (root / "artifacts" / "benchmark-last.json").write_text(
        json.dumps(
            {
                "benchmark": "line-follower",
                "robot_profile": "monsterborg-4wd",
                "runtime_target": "interactive-webots",
                "track_variant": "baseline",
                "line_reacquisition_events": reacq,
                "max_line_reacquisition_steps": reacq_steps,
                "extra_metrics": {
                    "mean_forward_speed": mean_forward_speed,
                    "encoder_distance": encoder_distance,
                    "heading_drift": heading_drift,
                    "collision_count": 0,
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def test_monsterborg_calibration_report_passes_when_deltas_are_small(tmp_path: Path) -> None:
    sim_root = tmp_path / "sim"
    physical_root = tmp_path / "physical"
    _write_export(sim_root, mean_forward_speed=4.0, encoder_distance=2.1, heading_drift=0.22, reacq=1, reacq_steps=4)
    _write_export(physical_root, mean_forward_speed=3.7, encoder_distance=2.0, heading_drift=0.2, reacq=1, reacq_steps=4)
    payload = build_calibration_report(sim_export=sim_root, physical_export=physical_root)
    assert payload["pass"] is True
    assert payload["track_variant"] == "baseline"


def test_monsterborg_calibration_report_fails_when_delta_exceeds_budget(tmp_path: Path) -> None:
    sim_root = tmp_path / "sim"
    physical_root = tmp_path / "physical"
    _write_export(sim_root, mean_forward_speed=4.0, encoder_distance=2.1, heading_drift=0.22, reacq=1, reacq_steps=4)
    _write_export(physical_root, mean_forward_speed=2.5, encoder_distance=1.2, heading_drift=0.5, reacq=4, reacq_steps=8)
    payload = build_calibration_report(sim_export=sim_root, physical_export=physical_root)
    assert payload["pass"] is False
    assert payload["failures"]
