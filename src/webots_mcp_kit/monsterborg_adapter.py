from __future__ import annotations

import importlib.util
import json
import os
import platform
from pathlib import Path
from typing import Any

from .models import (
    SESSION_EXPORT_ARTIFACT_STANDARD_VERSION,
    SESSION_EXPORT_STANDARD_ARTIFACTS,
    SessionExport,
)
from .utils import atomic_write_text, utc_now_iso


def _module_available(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def _detect_pi_model() -> str | None:
    candidates = [
        Path("/proc/device-tree/model"),
        Path("/sys/firmware/devicetree/base/model"),
    ]
    for candidate in candidates:
        try:
            if candidate.exists():
                return candidate.read_text(encoding="utf-8", errors="ignore").strip("\x00 \n")
        except OSError:
            continue
    return None


def verify_monsterborg_physical_environment(*, camera_required: bool = True) -> dict[str, Any]:
    module_status = {
        "ThunderBorg3": _module_available("ThunderBorg3"),
        "picamera2": _module_available("picamera2"),
        "smbus2": _module_available("smbus2"),
    }
    pi_model = _detect_pi_model()
    ready = module_status["ThunderBorg3"] and module_status["smbus2"] and (module_status["picamera2"] or not camera_required)
    missing = [name for name, present in module_status.items() if not present and (camera_required or name != "picamera2")]
    if ready:
        status = "ready"
        summary = "MonsterBorg physical adapter prerequisites are available."
        next_step = "Run `python scripts/monsterborg_capture_run.py --input <capture.json> --output <export-dir>` after collecting telemetry on the Pi."
    else:
        status = "blocked"
        summary = "MonsterBorg physical adapter prerequisites are incomplete."
        next_step = "Install the missing MonsterBorg Raspberry Pi dependencies, then rerun this verification command."
    return {
        "status": status,
        "summary": summary,
        "support_tier": "experimental-foundation",
        "robot_family": "monsterborg",
        "robot_profile": "monsterborg-4wd",
        "runtime_target": "monsterborg-physical",
        "platform": {
            "system": platform.system(),
            "machine": platform.machine(),
            "python_version": platform.python_version(),
            "pi_model": pi_model,
            "hostname": platform.node(),
        },
        "module_status": module_status,
        "camera_required": camera_required,
        "missing_modules": missing,
        "next_step": next_step,
    }


def _runtime_summary_from_samples(samples: list[dict[str, Any]]) -> dict[str, Any]:
    last = samples[-1] if samples else {}
    sensors = last.get("sensors", {}) if isinstance(last.get("sensors"), dict) else {}
    metrics = last.get("metrics", {}) if isinstance(last.get("metrics"), dict) else {}
    actuators = last.get("actuators", {}) if isinstance(last.get("actuators"), dict) else {}
    state = last.get("state", {}) if isinstance(last.get("state"), dict) else {}
    return {
        "agent": {
            "connected": True,
            "device_count": 9,
            "sensor_keys": sorted(sensors),
            "metric_keys": sorted(metrics),
            "actuator_keys": sorted(actuators),
            "state_keys": sorted(state),
        },
        "physical_adapter": {
            "connected": True,
            "device_count": 0,
            "sensor_keys": [],
            "metric_keys": [],
            "actuator_keys": [],
            "state_keys": ["runtime_target", "samples_recorded"],
        },
    }


def _physical_task_metrics(samples: list[dict[str, Any]], *, benchmark_name: str, task_variant: str) -> dict[str, Any]:
    if not samples:
        base = {
            "mean_forward_speed": 0.0,
            "encoder_distance": 0.0,
            "heading_drift": 0.0,
            "collision_count": 0,
            "task_variant": task_variant,
        }
        if benchmark_name == "line-follower":
            base.update(
                {
                    "line_reacquisition_events": 0,
                    "max_line_reacquisition_steps": 0,
                    "camera_signal_strength_mean": 0.0,
                }
            )
        elif benchmark_name == "obstacle-avoidance":
            base.update(
                {
                    "min_front_range": 0.0,
                    "obstacle_clearance_violations": 0,
                    "heading_recovery_events": 0,
                    "stalled_steps": 0,
                    "speed_envelope_violations": 0,
                }
            )
        else:
            base.update(
                {
                    "progress_ratio": 0.0,
                    "distance_to_goal_final": 0.0,
                    "heading_alignment_error": 0.0,
                    "path_deviation_score": 0.0,
                    "waypoint_recovery_events": 0,
                    "stalled_steps": 0,
                }
            )
        return base
    mean_forward_speed_sum = 0.0
    signal_strength_sum = 0.0
    line_reacquisition_events = 0
    max_line_reacquisition_steps = 0
    current_loss_steps = 0
    collision_count = 0
    previous_left = None
    previous_right = None
    encoder_distance = 0.0
    first_heading = None
    last_heading = None
    min_front_range = float("inf")
    obstacle_clearance_violations = 0
    heading_recovery_events = 0
    stalled_steps = 0
    speed_envelope_violations = 0
    progress_ratio = 0.0
    distance_to_goal_final = None
    heading_alignment_error = 0.0
    path_deviation_sum = 0.0
    path_deviation_samples = 0
    waypoint_recovery_events = 0
    for sample in samples:
        sensors = sample.get("sensors", {}) if isinstance(sample.get("sensors"), dict) else {}
        metrics = sample.get("metrics", {}) if isinstance(sample.get("metrics"), dict) else {}
        mean_forward_speed_sum += abs(float(metrics.get("mean_forward_speed", 0.0)))
        signal_strength_sum += float(metrics.get("camera_signal_strength", 0.0))
        line_visible = bool(metrics.get("line_visible", False))
        if line_visible:
            if current_loss_steps > 0:
                line_reacquisition_events += 1
                max_line_reacquisition_steps = max(max_line_reacquisition_steps, current_loss_steps)
            current_loss_steps = 0
        else:
            current_loss_steps += 1
        collision_count += int(metrics.get("collision_events", 0))
        heading = sensors.get("heading")
        if heading is not None and first_heading is None:
            first_heading = float(heading)
        if heading is not None:
            last_heading = float(heading)
        left = sensors.get("left_encoder")
        right = sensors.get("right_encoder")
        if previous_left is not None and previous_right is not None and left is not None and right is not None:
            left_delta = float(left) - float(previous_left)
            right_delta = float(right) - float(previous_right)
            encoder_distance += abs((left_delta + right_delta) / 2.0) * 0.05
        previous_left = left
        previous_right = right
        front_range = sensors.get("front_range")
        if front_range is not None:
            min_front_range = min(min_front_range, float(front_range))
        obstacle_clearance_violations += int(metrics.get("clearance_violation", 0) or 0)
        heading_recovery_events = max(heading_recovery_events, int(metrics.get("heading_recovery_events", 0) or 0))
        stalled_steps = max(stalled_steps, int(metrics.get("stalled_steps", 0) or 0))
        speed_envelope_violations += int(metrics.get("speed_saturation", 0) or 0)
        progress_ratio = max(progress_ratio, float(metrics.get("progress_ratio", 0.0) or 0.0))
        if metrics.get("distance_to_goal_estimate") is not None:
            distance_to_goal_final = float(metrics.get("distance_to_goal_estimate"))
        heading_alignment_error = max(heading_alignment_error, float(metrics.get("heading_alignment_error", 0.0) or 0.0))
        path_deviation_sum += float(metrics.get("path_deviation_score", 0.0) or 0.0)
        path_deviation_samples += 1
        waypoint_recovery_events = max(waypoint_recovery_events, int(metrics.get("waypoint_recovery_events", 0) or 0))
    max_line_reacquisition_steps = max(max_line_reacquisition_steps, current_loss_steps)
    payload = {
        "mean_forward_speed": round(mean_forward_speed_sum / max(len(samples), 1), 6),
        "encoder_distance": round(encoder_distance, 6),
        "heading_drift": round(abs(float(last_heading or 0.0) - float(first_heading or 0.0)), 6),
        "collision_count": collision_count,
        "task_variant": task_variant,
    }
    if benchmark_name == "line-follower":
        payload.update(
            {
                "camera_signal_strength_mean": round(signal_strength_sum / max(len(samples), 1), 6),
                "line_reacquisition_events": line_reacquisition_events,
                "max_line_reacquisition_steps": max_line_reacquisition_steps,
                "track_variant": task_variant,
            }
        )
    elif benchmark_name == "obstacle-avoidance":
        payload.update(
            {
                "min_front_range": round(0.0 if min_front_range == float("inf") else min_front_range, 6),
                "obstacle_clearance_violations": obstacle_clearance_violations,
                "heading_recovery_events": heading_recovery_events,
                "stalled_steps": stalled_steps,
                "speed_envelope_violations": speed_envelope_violations,
            }
        )
    else:
        payload.update(
            {
                "progress_ratio": round(progress_ratio, 6),
                "distance_to_goal_final": round(float(distance_to_goal_final or 0.0), 6),
                "heading_alignment_error": round(heading_alignment_error, 6),
                "path_deviation_score": round(path_deviation_sum / max(path_deviation_samples, 1), 6),
                "waypoint_recovery_events": waypoint_recovery_events,
                "stalled_steps": stalled_steps,
            }
        )
    return payload


def build_monsterborg_physical_bundle(
    *,
    output_dir: Path,
    scenario: str,
    robot_name: str,
    samples: list[dict[str, Any]],
    benchmark_name: str | None = None,
    benchmark_report: dict[str, Any] | None = None,
    physical_adapter_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    export_dir = output_dir if output_dir.is_absolute() else (Path.cwd() / output_dir).resolve()
    export_dir.mkdir(parents=True, exist_ok=True)
    artifacts_dir = export_dir / "artifacts"
    artifacts_dir.mkdir(exist_ok=True)

    verify_payload = verify_monsterborg_physical_environment()
    physical_summary = physical_adapter_summary or {
        "runtime_target": "monsterborg-physical",
        "samples_recorded": len(samples),
        "verification_status": verify_payload["status"],
        "pi_model": verify_payload["platform"].get("pi_model"),
        "module_status": verify_payload["module_status"],
    }

    session_id = f"monsterborg-physical-{scenario}"
    standard_artifacts = {name: str(export_dir / filename) for name, filename in SESSION_EXPORT_STANDARD_ARTIFACTS}
    samples_path = artifacts_dir / "monsterborg_physical_samples.json"
    atomic_write_text(samples_path, json.dumps(samples, indent=2), encoding="utf-8")
    resolved_benchmark_name = benchmark_name or scenario
    resolved_variant = "baseline"
    if isinstance(benchmark_report, dict):
        resolved_variant = str(benchmark_report.get("task_variant") or benchmark_report.get("track_variant") or resolved_variant)
    if isinstance(physical_adapter_summary, dict):
        resolved_variant = str(physical_adapter_summary.get("task_variant") or resolved_variant)
    derived_task_metrics = _physical_task_metrics(samples, benchmark_name=resolved_benchmark_name, task_variant=resolved_variant)

    runtime_summary = _runtime_summary_from_samples(samples)
    session_payload = {
        "session_id": session_id,
        "host": "",
        "port": 0,
        "daemon_pid": 0,
        "status": "completed",
        "scenario": scenario,
        "world": "<physical-monsterborg>",
        "mode": "physical",
        "render": False,
        "robot_controller": "<physical-adapter>",
        "target_robot_name": robot_name,
        "target_robot_def": "MONSTERBORG",
        "created_at": utc_now_iso(),
        "session_dir": str(export_dir),
        "artifacts_dir": str(artifacts_dir),
        "robot_family": "monsterborg",
        "robot_profile": "monsterborg-4wd",
        "runtime_target": "monsterborg-physical",
        "stopped_at": utc_now_iso(),
        "last_error": None,
        "last_error_code": None,
        "last_error_details": {},
        "environment": {
            "runtime_target": "monsterborg-physical",
            "platform": verify_payload["platform"],
            "module_status": verify_payload["module_status"],
        },
        "runtime_summary": runtime_summary,
    }

    last_sample = samples[-1] if samples else {}
    inspect_payload = {
        "manifest": session_payload,
        "session_state": {
            "status": "completed",
            "created_at": session_payload["created_at"],
            "stopped_at": session_payload["stopped_at"],
            "last_error_code": None,
            "last_error": None,
            "target_robot_name": robot_name,
            "scenario": scenario,
        },
        "artifacts": [{"name": samples_path.name, "path": str(samples_path), "size": samples_path.stat().st_size}],
        "logs": [],
        "log_summary": {},
        "runtime_state": {
            "session": session_payload,
            "session_state": {"status": "completed", "scenario": scenario, "target_robot_name": robot_name},
            "control_paused": False,
            "runtime_summary": runtime_summary,
            "runtimes": {
                "agent": {
                    "role": "agent",
                    "name": robot_name,
                    "connected": True,
                    "devices": [],
                    "state": last_sample.get("state", {}) if isinstance(last_sample.get("state"), dict) else {},
                    "sensors": last_sample.get("sensors", {}) if isinstance(last_sample.get("sensors"), dict) else {},
                    "metrics": last_sample.get("metrics", {}) if isinstance(last_sample.get("metrics"), dict) else {},
                    "actuators": last_sample.get("actuators", {}) if isinstance(last_sample.get("actuators"), dict) else {},
                    "meta": {"runtime_target": "monsterborg-physical"},
                }
            },
        },
    }

    benchmark_payload = dict(benchmark_report) if isinstance(benchmark_report, dict) else {}
    benchmark_payload.setdefault("benchmark", resolved_benchmark_name)
    benchmark_payload.setdefault("pass", True)
    benchmark_payload.setdefault("session_mode", "physical")
    benchmark_payload.setdefault("robot_family", "monsterborg")
    benchmark_payload.setdefault("robot_profile", "monsterborg-4wd")
    benchmark_payload.setdefault("runtime_target", "monsterborg-physical")
    benchmark_payload.setdefault("notes", [])
    benchmark_payload["task_variant"] = str(benchmark_payload.get("task_variant") or derived_task_metrics["task_variant"])
    task_quality_summary = benchmark_payload.get("task_quality_summary") if isinstance(benchmark_payload.get("task_quality_summary"), dict) else {}
    benchmark_payload["task_quality_summary"] = {**derived_task_metrics, **task_quality_summary}
    if derived_task_metrics.get("track_variant") is not None:
        benchmark_payload["track_variant"] = str(benchmark_payload.get("track_variant") or derived_task_metrics["track_variant"])
    if "line_reacquisition_events" in derived_task_metrics:
        benchmark_payload["line_reacquisition_events"] = int(
            benchmark_payload.get("line_reacquisition_events", derived_task_metrics.get("line_reacquisition_events", 0)) or 0
        )
    if "max_line_reacquisition_steps" in derived_task_metrics:
        benchmark_payload["max_line_reacquisition_steps"] = int(
            benchmark_payload.get("max_line_reacquisition_steps", derived_task_metrics.get("max_line_reacquisition_steps", 0)) or 0
        )
    if "camera_signal_strength_mean" in derived_task_metrics:
        benchmark_payload["camera_signal_strength_mean"] = float(
            benchmark_payload.get("camera_signal_strength_mean", derived_task_metrics.get("camera_signal_strength_mean", 0.0)) or 0.0
        )
    extra_metrics = benchmark_payload.get("extra_metrics") if isinstance(benchmark_payload.get("extra_metrics"), dict) else {}
    benchmark_payload["extra_metrics"] = {**derived_task_metrics, **extra_metrics}
    benchmark_payload.setdefault("physical_adapter_summary", physical_summary)
    summary_payload = {
        "session_state": inspect_payload["session_state"],
        "runtime_summary": runtime_summary,
        "runtime_environment": session_payload["environment"],
        "benchmark_summary": {
            "benchmark_name": benchmark_payload.get("benchmark", benchmark_name or scenario),
            "result_reason": "completed" if benchmark_payload.get("pass", False) else "failed",
            "status": "completed" if benchmark_payload.get("pass", False) else "failed",
            "last_error_code": None,
            "rerun_supported": False,
            "next_step": "Inspect the replay output and compare the captured samples against the latest Webots benchmark.",
            "robot_family": "monsterborg",
            "robot_profile": "monsterborg-4wd",
            "runtime_target": "monsterborg-physical",
            "physical_adapter_summary": physical_summary,
            "task_variant": benchmark_payload.get("task_variant"),
            "task_quality_summary": benchmark_payload.get("task_quality_summary", {}),
            "track_variant": benchmark_payload.get("track_variant"),
            "line_reacquisition_events": benchmark_payload.get("line_reacquisition_events"),
            "max_line_reacquisition_steps": benchmark_payload.get("max_line_reacquisition_steps"),
            "camera_signal_strength_mean": benchmark_payload.get("camera_signal_strength_mean"),
        },
        "controller_fix_hints": benchmark_payload.get("controller_fix_hints", []),
        "telemetry_samples": len(samples),
        "physical_adapter_summary": physical_summary,
    }

    export_payload = SessionExport(
        export_dir=str(export_dir),
        session_id=session_id,
        manifest_path=standard_artifacts["session"],
        inspect_path=standard_artifacts["inspect"],
        log_inventory_path=standard_artifacts["log_inventory"],
        log_summary_path=standard_artifacts["log_summary"],
        runtime_environment_path=standard_artifacts["runtime_environment"],
        doctor_path=standard_artifacts["doctor"],
        summary_path=standard_artifacts["summary"],
        export_manifest_path=standard_artifacts["export_manifest"],
        artifact_standard_version=SESSION_EXPORT_ARTIFACT_STANDARD_VERSION,
        replay_mode="observability",
        standard_artifacts=standard_artifacts,
        copied_logs=[],
        copied_artifacts=[str(samples_path)],
        scenario=scenario,
        status="completed",
        last_error_code=None,
        result_reason="completed" if benchmark_payload.get("pass", False) else "failed",
    )

    atomic_write_text(Path(standard_artifacts["doctor"]), json.dumps(verify_payload, indent=2), encoding="utf-8")
    atomic_write_text(Path(standard_artifacts["session"]), json.dumps(session_payload, indent=2), encoding="utf-8")
    atomic_write_text(Path(standard_artifacts["inspect"]), json.dumps(inspect_payload, indent=2), encoding="utf-8")
    atomic_write_text(Path(standard_artifacts["log_inventory"]), json.dumps([], indent=2), encoding="utf-8")
    atomic_write_text(Path(standard_artifacts["log_summary"]), json.dumps({}, indent=2), encoding="utf-8")
    atomic_write_text(Path(standard_artifacts["runtime_environment"]), json.dumps(session_payload["environment"], indent=2), encoding="utf-8")
    atomic_write_text(Path(standard_artifacts["summary"]), json.dumps(summary_payload, indent=2), encoding="utf-8")
    atomic_write_text(Path(standard_artifacts["export_manifest"]), json.dumps(export_payload.to_dict(), indent=2), encoding="utf-8")
    atomic_write_text(artifacts_dir / "benchmark-last.json", json.dumps(benchmark_payload, indent=2), encoding="utf-8")

    return {
        "status": "completed",
        "summary": "MonsterBorg physical capture bundle is ready for replay.",
        "support_tier": "experimental-foundation",
        "robot_family": "monsterborg",
        "robot_profile": "monsterborg-4wd",
        "runtime_target": "monsterborg-physical",
        "export_dir": str(export_dir),
        "samples_path": str(samples_path),
        "artifact_standard_version": SESSION_EXPORT_ARTIFACT_STANDARD_VERSION,
        "physical_adapter_summary": physical_summary,
        "next_step": f'Run `webots-kit session replay "{export_dir}"` to inspect the physical capture bundle.',
    }
