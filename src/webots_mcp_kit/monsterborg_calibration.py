from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def resolve_export_root(path: Path) -> Path:
    resolved = path if path.is_absolute() else (Path.cwd() / path).resolve()
    return resolved.parent if resolved.is_file() else resolved


def load_export_metrics(path: Path) -> dict[str, Any]:
    export_root = resolve_export_root(path)
    summary_path = export_root / "summary.json"
    benchmark_path = export_root / "artifacts" / "benchmark-last.json"
    export_manifest_path = export_root / "export.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {}
    benchmark = json.loads(benchmark_path.read_text(encoding="utf-8")) if benchmark_path.exists() else {}
    export_manifest = json.loads(export_manifest_path.read_text(encoding="utf-8")) if export_manifest_path.exists() else {}
    benchmark_summary = summary.get("benchmark_summary", {}) if isinstance(summary.get("benchmark_summary"), dict) else {}
    extra_metrics = benchmark.get("extra_metrics", {}) if isinstance(benchmark.get("extra_metrics"), dict) else {}
    benchmark_name = benchmark.get("benchmark") or benchmark_summary.get("benchmark_name") or "line-follower"
    task_quality_summary = benchmark.get("task_quality_summary", {}) if isinstance(benchmark.get("task_quality_summary"), dict) else {}
    return {
        "export_root": str(export_root),
        "benchmark": benchmark_name,
        "robot_profile": benchmark.get("robot_profile") or summary.get("robot_profile") or "monsterborg-4wd",
        "runtime_target": benchmark.get("runtime_target") or summary.get("runtime_target"),
        "task_variant": benchmark.get("task_variant") or benchmark_summary.get("task_variant") or benchmark.get("track_variant") or benchmark_summary.get("track_variant") or "baseline",
        "task_quality_summary": task_quality_summary or benchmark_summary.get("task_quality_summary", {}),
        "mean_forward_speed": float(extra_metrics.get("mean_forward_speed", 0.0)),
        "encoder_distance": float(extra_metrics.get("encoder_distance", extra_metrics.get("odometry_travelled_distance", 0.0))),
        "heading_drift": float(extra_metrics.get("heading_drift", 0.0)),
        "line_reacquisition_events": int(benchmark.get("line_reacquisition_events", benchmark_summary.get("line_reacquisition_events", 0)) or 0),
        "max_line_reacquisition_steps": int(benchmark.get("max_line_reacquisition_steps", benchmark_summary.get("max_line_reacquisition_steps", 0)) or 0),
        "collision_count": int(extra_metrics.get("collision_count", extra_metrics.get("collision_events", 0)) or 0),
        "artifact_standard_version": int(export_manifest.get("artifact_standard_version", 1)),
    }


def delta_fraction(left: float, right: float) -> float:
    baseline = max(abs(left), abs(right), 1e-6)
    return abs(left - right) / baseline


def build_calibration_report(*, sim_export: Path, physical_export: Path) -> dict[str, Any]:
    sim_summary = load_export_metrics(sim_export)
    physical_summary = load_export_metrics(physical_export)
    benchmark_name = str(physical_summary.get("benchmark") or sim_summary.get("benchmark") or "line-follower")
    delta_summary = {
        "mean_forward_speed_delta": round(delta_fraction(sim_summary["mean_forward_speed"], physical_summary["mean_forward_speed"]), 6),
        "encoder_distance_delta": round(delta_fraction(sim_summary["encoder_distance"], physical_summary["encoder_distance"]), 6),
        "heading_drift_delta": round(delta_fraction(sim_summary["heading_drift"], physical_summary["heading_drift"]), 6),
        "line_reacquisition_events_delta": abs(int(sim_summary["line_reacquisition_events"]) - int(physical_summary["line_reacquisition_events"])),
        "max_line_reacquisition_steps_delta": round(
            delta_fraction(float(sim_summary["max_line_reacquisition_steps"]), float(physical_summary["max_line_reacquisition_steps"])),
            6,
        ),
        "collision_count_delta": abs(int(sim_summary["collision_count"]) - int(physical_summary["collision_count"])),
        "min_front_range_delta": round(
            delta_fraction(
                float(sim_summary.get("task_quality_summary", {}).get("min_front_range", 0.0)),
                float(physical_summary.get("task_quality_summary", {}).get("min_front_range", 0.0)),
            ),
            6,
        ),
        "stalled_steps_delta": round(
            delta_fraction(
                float(sim_summary.get("task_quality_summary", {}).get("stalled_steps", 0.0)),
                float(physical_summary.get("task_quality_summary", {}).get("stalled_steps", 0.0)),
            ),
            6,
        ),
        "progress_ratio_delta": round(
            delta_fraction(
                float(sim_summary.get("task_quality_summary", {}).get("progress_ratio", 0.0)),
                float(physical_summary.get("task_quality_summary", {}).get("progress_ratio", 0.0)),
            ),
            6,
        ),
        "distance_to_goal_final_delta": round(
            delta_fraction(
                float(sim_summary.get("task_quality_summary", {}).get("distance_to_goal_final", 0.0)),
                float(physical_summary.get("task_quality_summary", {}).get("distance_to_goal_final", 0.0)),
            ),
            6,
        ),
        "heading_alignment_error_delta": round(
            delta_fraction(
                float(sim_summary.get("task_quality_summary", {}).get("heading_alignment_error", 0.0)),
                float(physical_summary.get("task_quality_summary", {}).get("heading_alignment_error", 0.0)),
            ),
            6,
        ),
    }
    failures: list[str] = []
    if benchmark_name == "line-follower":
        if delta_summary["encoder_distance_delta"] > 0.20:
            failures.append("encoder_distance_delta")
        if delta_summary["mean_forward_speed_delta"] > 0.20:
            failures.append("mean_forward_speed_delta")
        if delta_summary["max_line_reacquisition_steps_delta"] > 0.25:
            failures.append("max_line_reacquisition_steps_delta")
        if delta_summary["heading_drift_delta"] > 0.20:
            failures.append("heading_drift_delta")
    elif benchmark_name == "obstacle-avoidance":
        if delta_summary["min_front_range_delta"] > 0.25:
            failures.append("min_front_range_delta")
        if delta_summary["mean_forward_speed_delta"] > 0.20:
            failures.append("mean_forward_speed_delta")
        if delta_summary["stalled_steps_delta"] > 0.20:
            failures.append("stalled_steps_delta")
        if delta_summary["collision_count_delta"] > 0:
            failures.append("collision_count_delta")
    else:
        if delta_summary["distance_to_goal_final_delta"] > 0.20:
            failures.append("distance_to_goal_final_delta")
        if delta_summary["progress_ratio_delta"] > 0.15:
            failures.append("progress_ratio_delta")
        if delta_summary["heading_alignment_error_delta"] > 0.20:
            failures.append("heading_alignment_error_delta")
        if delta_summary["mean_forward_speed_delta"] > 0.20:
            failures.append("mean_forward_speed_delta")
    passed = not failures
    return {
        "robot_profile": "monsterborg-4wd",
        "benchmark": benchmark_name,
        "task_variant": physical_summary.get("task_variant") or sim_summary.get("task_variant") or "baseline",
        "track_variant": physical_summary.get("task_variant") or sim_summary.get("task_variant") or "baseline",
        "sim_summary": sim_summary,
        "physical_summary": physical_summary,
        "delta_summary": delta_summary,
        "pass": passed,
        "failures": failures,
        "next_step": (
            "Calibration is within the supported parity window."
            if passed
            else "Adjust controller gains, camera placement, or physical adapter sampling, then capture a new physical export."
        ),
    }
