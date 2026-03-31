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
