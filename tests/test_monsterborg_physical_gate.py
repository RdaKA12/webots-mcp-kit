from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from webots_mcp_kit.monsterborg_calibration import build_calibration_report
from webots_mcp_kit.scenario_ops import replay_session


ROOT = Path(__file__).resolve().parents[1]
CAPTURE_FIXTURES = ROOT / "examples" / "monsterborg" / "physical-captures"


def _write_sim_export(root: Path, *, benchmark: str, variant: str, extra_metrics: dict[str, float], task_quality_summary: dict[str, float]) -> Path:
    export_root = root / benchmark
    artifacts = export_root / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    benchmark_payload = {
        "benchmark": benchmark,
        "pass": True,
        "robot_profile": "monsterborg-4wd",
        "runtime_target": "interactive-webots",
        "task_variant": variant,
        "track_variant": variant if benchmark == "line-follower" else None,
        "line_reacquisition_events": int(extra_metrics.get("line_reacquisition_events", 0) or 0),
        "max_line_reacquisition_steps": int(extra_metrics.get("max_line_reacquisition_steps", 0) or 0),
        "task_quality_summary": task_quality_summary,
        "extra_metrics": extra_metrics,
    }
    summary_payload = {
        "benchmark_summary": {
            "benchmark_name": benchmark,
            "task_variant": variant,
            "task_quality_summary": task_quality_summary,
            "result_reason": "completed",
            "status": "completed",
        },
        "runtime_environment": {"runtime_target": "interactive-webots"},
    }
    export_payload = {"artifact_standard_version": 1}
    (artifacts / "benchmark-last.json").write_text(json.dumps(benchmark_payload, indent=2), encoding="utf-8")
    (export_root / "summary.json").write_text(json.dumps(summary_payload, indent=2), encoding="utf-8")
    (export_root / "export.json").write_text(json.dumps(export_payload, indent=2), encoding="utf-8")
    return export_root


def _run_script(script: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / script), *args],
        check=True,
        capture_output=True,
        text=True,
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
    )


def test_monsterborg_physical_operator_flow_for_all_tasks(tmp_path: Path) -> None:
    sim_root = tmp_path / "sim"
    sim_exports = {
        "line-follower": _write_sim_export(
            sim_root,
            benchmark="line-follower",
            variant="baseline",
            extra_metrics={
                "mean_forward_speed": 0.285,
                "encoder_distance": 0.158,
                "heading_drift": 0.028,
                "collision_count": 0,
                "line_reacquisition_events": 1,
                "max_line_reacquisition_steps": 1,
            },
            task_quality_summary={
                "oscillation_score": 0.16,
                "speed_envelope_violations": 0,
            },
        ),
        "obstacle-avoidance": _write_sim_export(
            sim_root,
            benchmark="obstacle-avoidance",
            variant="baseline",
            extra_metrics={
                "mean_forward_speed": 0.22,
                "encoder_distance": 0.1,
                "heading_drift": 0.05,
                "collision_count": 0,
            },
            task_quality_summary={
                "min_front_range": 0.25,
                "obstacle_clearance_violations": 1,
                "heading_recovery_events": 2,
                "stalled_steps": 1,
                "collision_events": 0,
                "speed_envelope_violations": 1,
            },
        ),
        "waypoint-nav": _write_sim_export(
            sim_root,
            benchmark="waypoint-nav",
            variant="baseline",
            extra_metrics={
                "mean_forward_speed": 0.24,
                "encoder_distance": 0.135,
                "heading_drift": 0.095,
                "collision_count": 0,
            },
            task_quality_summary={
                "progress_ratio": 0.95,
                "distance_to_goal_final": 0.11,
                "heading_alignment_error": 0.13,
                "path_deviation_score": 0.12,
                "waypoint_recovery_events": 1,
                "stalled_steps": 1,
            },
        ),
    }

    physical_exports: list[Path] = []
    for benchmark in ("line-follower", "obstacle-avoidance", "waypoint-nav"):
        capture_path = CAPTURE_FIXTURES / f"{benchmark}.capture.json"
        physical_export = tmp_path / "physical" / benchmark
        _run_script(
            "monsterborg_capture_run.py",
            "--input",
            str(capture_path),
            "--output",
            str(physical_export),
            "--scenario",
            benchmark,
            "--benchmark",
            benchmark,
            "--variant",
            "baseline",
        )
        replay = replay_session(physical_export)
        assert replay["task_variant"] == "baseline"
        assert replay["task_quality_summary"]
        assert replay["runtime_environment"]["runtime_target"] == "monsterborg-physical"

        calibration = build_calibration_report(sim_export=sim_exports[benchmark], physical_export=physical_export)
        assert calibration["benchmark"] == benchmark
        assert calibration["task_variant"] == "baseline"
        assert calibration["pass"] is True
        physical_exports.append(physical_export)

    matrix_output = tmp_path / "monsterborg-matrix.json"
    _run_script("monsterborg_benchmark_matrix.py", *(str(path) for path in physical_exports), "--output", str(matrix_output))
    matrix_payload = json.loads(matrix_output.read_text(encoding="utf-8"))
    assert matrix_payload["robot_profile"] == "monsterborg-4wd"
    assert len(matrix_payload["entries"]) == 3
    assert {entry["task"] for entry in matrix_payload["entries"]} == {
        "line-follower",
        "obstacle-avoidance",
        "waypoint-nav",
    }
