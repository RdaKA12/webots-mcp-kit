from __future__ import annotations

import json
from pathlib import Path

from webots_mcp_kit.monsterborg_matrix import build_benchmark_matrix


def test_monsterborg_benchmark_matrix_aggregates_reports_and_exports(tmp_path: Path) -> None:
    line_report = tmp_path / "line-report.json"
    line_report.write_text(
        json.dumps(
            {
                "benchmark": "line-follower",
                "pass": True,
                "robot_profile": "monsterborg-4wd",
                "runtime_target": "interactive-webots",
                "task_variant": "baseline",
                "task_quality_summary": {"oscillation_score": 0.2},
                "controller_fix_hints": ["Lower turn gain slightly."],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    export_dir = tmp_path / "waypoint-export"
    (export_dir / "artifacts").mkdir(parents=True)
    (export_dir / "artifacts" / "benchmark-last.json").write_text(
        json.dumps(
            {
                "benchmark": "waypoint-nav",
                "pass": False,
                "robot_profile": "monsterborg-4wd",
                "runtime_target": "monsterborg-physical",
                "task_variant": "offset-start",
                "task_quality_summary": {"progress_ratio": 0.74},
                "notes": ["target-not-reached"],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (export_dir / "summary.json").write_text(
        json.dumps({"benchmark_summary": {"benchmark_name": "waypoint-nav", "task_variant": "offset-start"}}, indent=2),
        encoding="utf-8",
    )
    (export_dir / "export.json").write_text(json.dumps({"artifact_standard_version": 1}, indent=2), encoding="utf-8")

    payload = build_benchmark_matrix([line_report, export_dir])
    assert payload["robot_profile"] == "monsterborg-4wd"
    assert len(payload["entries"]) == 2
    assert any(entry["task"] == "line-follower" and entry["variant"] == "baseline" for entry in payload["entries"])
    assert any(entry["task"] == "waypoint-nav" and entry["variant"] == "offset-start" for entry in payload["entries"])
    repeatability = {(row["task"], row["variant"]): row for row in payload["repeatability_summary"]}
    assert repeatability[("line-follower", "baseline")]["pass_rate"] == 1.0
    assert repeatability[("waypoint-nav", "offset-start")]["pass_rate"] == 0.0
