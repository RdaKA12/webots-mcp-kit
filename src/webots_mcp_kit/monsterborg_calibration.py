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
    return {
        "export_root": str(export_root),
        "robot_profile": benchmark.get("robot_profile") or summary.get("robot_profile") or "monsterborg-4wd",
        "runtime_target": benchmark.get("runtime_target") or summary.get("runtime_target"),
        "track_variant": benchmark.get("track_variant") or benchmark_summary.get("track_variant") or "baseline",
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
    }
    failures: list[str] = []
    if delta_summary["encoder_distance_delta"] > 0.20:
        failures.append("encoder_distance_delta")
    if delta_summary["mean_forward_speed_delta"] > 0.20:
        failures.append("mean_forward_speed_delta")
    if delta_summary["max_line_reacquisition_steps_delta"] > 0.25:
        failures.append("max_line_reacquisition_steps_delta")
    if delta_summary["heading_drift_delta"] > 0.20:
        failures.append("heading_drift_delta")
    passed = not failures
    return {
        "robot_profile": "monsterborg-4wd",
        "track_variant": physical_summary.get("track_variant") or sim_summary.get("track_variant") or "baseline",
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
