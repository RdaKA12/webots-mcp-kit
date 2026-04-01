from __future__ import annotations

import json
from pathlib import Path

from webots_mcp_kit.benchmark import format_benchmark_report


def test_benchmark_report_formatting(tmp_path: Path) -> None:
    report_path = tmp_path / "report.json"
    report_path.write_text(
        json.dumps(
            {
                "benchmark": "line-follower",
                "world": "world.wbt",
                "controller": "example",
                "session_mode": "fast",
                "sim_time_s": 20.0,
                "steps": 100,
                "line_loss_events": 1,
                "max_line_loss_streak": 2,
                "mean_center_error": 0.1,
                "ir_balance_error": 0.2,
                "pass": True,
                "artifacts": {},
                "notes": [],
            }
        ),
        encoding="utf-8",
    )
    formatted = format_benchmark_report(report_path)
    assert "benchmark: line-follower" in formatted
    assert "result: pass (completed)" in formatted


def test_benchmark_report_formatting_waypoint_fields(tmp_path: Path) -> None:
    report_path = tmp_path / "waypoint-report.json"
    report_path.write_text(
        json.dumps(
            {
                "benchmark": "waypoint-nav",
                "world": "world.wbt",
                "controller": "example",
                "session_mode": "fast",
                "sim_time_s": 12.0,
                "steps": 30,
                "line_loss_events": 0,
                "max_line_loss_streak": 0,
                "mean_center_error": 0.0,
                "ir_balance_error": 0.0,
                "pass": False,
                "artifacts": {},
                "notes": ["target-not-reached"],
                "extra_metrics": {
                    "collision_events": 0,
                    "travelled_distance": 0.42,
                    "mean_forward_speed": 1.25,
                    "target_reached": False,
                    "target_distance": 0.3,
                },
            }
        ),
        encoding="utf-8",
    )
    formatted = format_benchmark_report(report_path)
    assert "result: fail (target-not-reached)" in formatted
    assert "target_reached: False" in formatted
    assert "target_distance: 0.3" in formatted
