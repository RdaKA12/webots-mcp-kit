from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .monsterborg_calibration import resolve_export_root


def load_benchmark_source(path: Path) -> dict[str, Any]:
    resolved = path if path.is_absolute() else (Path.cwd() / path).resolve()
    if resolved.is_file() and resolved.suffix.lower() == ".json":
        payload = json.loads(resolved.read_text(encoding="utf-8"))
        if "benchmark" in payload and "pass" in payload:
            return payload
        export_root = resolve_export_root(resolved)
    else:
        export_root = resolve_export_root(resolved)
    benchmark_path = export_root / "artifacts" / "benchmark-last.json"
    summary_path = export_root / "summary.json"
    benchmark_payload = json.loads(benchmark_path.read_text(encoding="utf-8")) if benchmark_path.exists() else {}
    summary_payload = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {}
    benchmark_summary = summary_payload.get("benchmark_summary", {}) if isinstance(summary_payload.get("benchmark_summary"), dict) else {}
    result_reason = benchmark_summary.get("result_reason", "completed")
    return {
        "benchmark": benchmark_payload.get("benchmark") or benchmark_summary.get("benchmark_name") or "unknown",
        "pass": bool(benchmark_payload.get("pass", True)),
        "robot_profile": benchmark_payload.get("robot_profile", "monsterborg-4wd"),
        "runtime_target": benchmark_payload.get("runtime_target", "interactive-webots"),
        "task_variant": benchmark_payload.get("task_variant") or benchmark_summary.get("task_variant") or benchmark_payload.get("track_variant") or "baseline",
        "task_quality_summary": benchmark_payload.get("task_quality_summary", benchmark_summary.get("task_quality_summary", {})),
        "notes": benchmark_payload.get("notes", [result_reason]),
        "controller_fix_hints": benchmark_payload.get("controller_fix_hints", summary_payload.get("controller_fix_hints", [])),
        "source_path": str(resolved),
    }


def _recommended_tuning_direction(payload: dict[str, Any]) -> str:
    hints = payload.get("controller_fix_hints")
    if isinstance(hints, list) and hints:
        return str(hints[0])
    benchmark = str(payload.get("benchmark") or "")
    summary = payload.get("task_quality_summary", {}) if isinstance(payload.get("task_quality_summary"), dict) else {}
    if benchmark == "line-follower" and float(summary.get("oscillation_score", 0.0) or 0.0) > 0.4:
        return "Lower turn gain or increase line filtering."
    if benchmark == "obstacle-avoidance" and int(summary.get("obstacle_clearance_violations", 0) or 0) > 0:
        return "Increase clearance margin or start recovery earlier."
    if benchmark == "waypoint-nav" and float(summary.get("progress_ratio", 0.0) or 0.0) < 0.85:
        return "Increase forward progress once heading is aligned."
    return "Inspect the benchmark report and session replay together before retuning."


def build_benchmark_matrix(paths: list[Path]) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    aggregates: dict[tuple[str, str], dict[str, Any]] = {}
    for path in paths:
        payload = load_benchmark_source(path)
        task = str(payload.get("benchmark") or "unknown")
        variant = str(payload.get("task_variant") or payload.get("track_variant") or "baseline")
        entry = {
            "task": task,
            "variant": variant,
            "pass": bool(payload.get("pass")),
            "runtime_target": payload.get("runtime_target"),
            "quality_metrics": payload.get("task_quality_summary", {}),
            "recommended_tuning_direction": _recommended_tuning_direction(payload),
            "source_path": payload.get("source_path", str(path)),
        }
        entries.append(entry)
        aggregate = aggregates.setdefault(
            (task, variant),
            {"task": task, "variant": variant, "runs": 0, "passes": 0, "pass_rate": 0.0},
        )
        aggregate["runs"] += 1
        aggregate["passes"] += 1 if entry["pass"] else 0
        aggregate["pass_rate"] = round(aggregate["passes"] / max(aggregate["runs"], 1), 6)
    return {
        "robot_profile": "monsterborg-4wd",
        "entries": entries,
        "repeatability_summary": sorted(aggregates.values(), key=lambda item: (item["task"], item["variant"])),
    }
