from __future__ import annotations

import json
from pathlib import Path

from .benchmarks import get_scenario, scenario_registry
from .robot_profiles import get_robot_profile, robot_profile_names
from .client import SessionClient
from .controller_authoring import detect_controller_language
from .launcher import start_session
from .models import BenchmarkReport


def list_benchmarks() -> list[dict[str, str]]:
    payload: list[dict[str, str]] = []
    for robot_profile in robot_profile_names():
        for scenario in scenario_registry(robot_profile=robot_profile).values():
            payload.append(
                {
                    "name": scenario.name,
                    "description": scenario.description,
                    "benchmark_kind": scenario.benchmark_kind,
                    "robot_family": scenario.robot_family,
                    "robot_profile": scenario.robot_profile,
                    "world": str(scenario.world),
                    "controller": str(scenario.controller),
                }
            )
    return payload


def run_benchmark(
    *,
    scenario: str,
    controller: str | None,
    output: Path,
    robot_profile: str | None = None,
    duration_s: float = 20.0,
    world: str | None = None,
    robot_name: str | None = None,
    robot_def: str | None = None,
) -> BenchmarkReport:
    scenario_def = get_scenario(scenario, robot_profile=robot_profile)
    profile = get_robot_profile(scenario_def.robot_profile)
    session = start_session(
        world=world,
        controller=controller,
        mode="fast",
        render=False,
        scenario=scenario,
        robot_profile=scenario_def.robot_profile,
        robot_name=robot_name,
        robot_def=robot_def,
    )
    client = SessionClient(session)
    try:
        request_payload = {"benchmark": scenario, "duration_s": duration_s, **scenario_def.benchmark_thresholds}
        result = client.request("run_benchmark", request_payload, timeout=_benchmark_request_timeout(controller, duration_s))
        report = BenchmarkReport(
            benchmark=result["benchmark"],
            world=result["world"],
            controller=result["controller"],
            session_mode=result["session_mode"],
            robot_family=result.get("robot_family") or scenario_def.robot_family,
            robot_profile=result.get("robot_profile") or scenario_def.robot_profile,
            runtime_target=result.get("runtime_target") or "interactive-webots",
            sim_time_s=result["sim_time_s"],
            steps=result["steps"],
            line_loss_events=result["line_loss_events"],
            max_line_loss_streak=result["max_line_loss_streak"],
            mean_center_error=result["mean_center_error"],
            ir_balance_error=result["ir_balance_error"],
            passed=result["pass"],
            artifacts=result["artifacts"],
            notes=result["notes"],
            extra_metrics=result.get("extra_metrics", {}),
            physical_adapter_summary=result.get("physical_adapter_summary", {}),
            controller_fix_hints=controller_fix_hints(
                scenario,
                result["notes"][0] if result.get("notes") else "completed",
                robot_profile=profile.robot_profile,
            ),
            missing_telemetry_keys=[],
            device_binding_hints=device_binding_hints(
                scenario,
                result["notes"][0] if result.get("notes") else "completed",
                robot_profile=profile.robot_profile,
            ),
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
        return report
    finally:
        try:
            client.request("stop", timeout=10.0)
        except Exception:
            pass


def run_line_follower_benchmark(
    *,
    controller: str | None,
    output: Path,
    duration_s: float = 20.0,
    world: str | None = None,
    robot_name: str | None = None,
    robot_def: str | None = None,
) -> BenchmarkReport:
    return run_benchmark(
        scenario="line-follower",
        controller=controller,
        output=output,
        robot_profile="e-puck",
        duration_s=duration_s,
        world=world,
        robot_name=robot_name,
        robot_def=robot_def,
    )


def format_benchmark_report(path: Path) -> str:
    data = json.loads(path.read_text(encoding="utf-8"))
    result_reason = data["notes"][0] if data.get("notes") else "completed"
    extra_metrics = data.get("extra_metrics", {})
    fix_hints = data.get("controller_fix_hints", [])
    missing_telemetry_keys = data.get("missing_telemetry_keys", [])
    binding_hints = data.get("device_binding_hints", [])
    next_step = benchmark_next_step(data["benchmark"], result_reason)
    lines = [
        f"benchmark: {data['benchmark']}",
        f"result: {'pass' if data['pass'] else 'fail'} ({result_reason})",
        f"robot_family: {data.get('robot_family')}",
        f"robot_profile: {data.get('robot_profile')}",
        f"runtime_target: {data.get('runtime_target')}",
        f"world: {data['world']}",
        f"controller: {data['controller']}",
        f"session_mode: {data['session_mode']}",
        f"sim_time_s: {data['sim_time_s']}",
        f"steps: {data['steps']}",
        f"line_loss_events: {data['line_loss_events']}",
        f"max_line_loss_streak: {data['max_line_loss_streak']}",
        f"mean_center_error: {data['mean_center_error']}",
        f"ir_balance_error: {data['ir_balance_error']}",
        f"next_step: {next_step}",
        f"artifacts: {data['artifacts']}",
        f"notes: {data['notes']}",
    ]
    if data["benchmark"] in {"obstacle-avoidance", "waypoint-nav"}:
        lines.append(f"collision_events: {extra_metrics.get('collision_events')}")
        lines.append(f"travelled_distance: {extra_metrics.get('travelled_distance')}")
        lines.append(f"mean_forward_speed: {extra_metrics.get('mean_forward_speed')}")
    if data["benchmark"] == "waypoint-nav":
        lines.append(f"target_reached: {extra_metrics.get('target_reached')}")
        lines.append(f"target_distance: {extra_metrics.get('target_distance')}")
    if extra_metrics:
        lines.append(f"extra_metrics: {extra_metrics}")
    if missing_telemetry_keys:
        lines.append(f"missing_telemetry_keys: {missing_telemetry_keys}")
    if binding_hints:
        lines.append(f"device_binding_hints: {binding_hints}")
    if fix_hints:
        lines.append(f"controller_fix_hints: {fix_hints}")
    return "\n".join(lines)


def benchmark_next_step(benchmark: str, result_reason: str) -> str:
    if result_reason == "completed":
        return "Use `webots-kit mcp serve` or run a longer benchmark to inspect live telemetry."
    if result_reason == "line-loss-threshold-reached":
        return "Inspect camera metrics and center_error, then tune the controller around line reacquisition."
    if result_reason == "collision-detected":
        return "Inspect proximity telemetry and contact-point metrics to reduce obstacle hits."
    if result_reason in {"target-not-reached", "low-travel-distance"}:
        return "Inspect waypoint progress and forward-speed metrics, then rerun with session logs enabled."
    if result_reason == "insufficient-forward-speed":
        return "Inspect actuator outputs and pause/manual-override state before rerunning the benchmark."
    return f"Review session artifacts and logs for benchmark `{benchmark}` before rerunning."


def _benchmark_request_timeout(controller: str | None, duration_s: float) -> float:
    timeout = max(duration_s * 6.0 + 30.0, 90.0)
    if controller:
        controller_path = Path(controller)
        if detect_controller_language(controller_path) == "cpp":
            timeout = max(timeout, duration_s * 8.0 + 45.0, 120.0)
    return timeout


def controller_fix_hints(benchmark: str, result_reason: str, *, robot_profile: str = "e-puck") -> list[str]:
    hints: list[str] = []
    if result_reason == "line-loss-threshold-reached":
        hints.append("Tune the control policy around camera-based line reacquisition.")
        hints.append("Verify report_step emits the expected camera and line metrics.")
    if result_reason == "collision-detected":
        hints.append("Review proximity-sensor telemetry and obstacle-pressure logic.")
    if result_reason in {"target-not-reached", "low-travel-distance"}:
        hints.append("Increase goal-seeking forward progress and review waypoint control logic.")
    if result_reason == "insufficient-forward-speed":
        hints.append("Check actuator outputs and symbol constants that cap wheel speed.")
    if benchmark in {"obstacle-avoidance", "waypoint-nav"}:
        if robot_profile == "monsterborg-4wd":
            hints.append("Ensure front_range, heading, yaw_rate, left_encoder, and right_encoder are exposed in report_step sensors.")
        else:
            hints.append("Ensure all ps0-ps7 readings are exposed in report_step sensors.")
    return sorted(dict.fromkeys(hints))


def device_binding_hints(benchmark: str, result_reason: str, *, robot_profile: str = "e-puck") -> list[str]:
    camera_name = get_robot_profile(robot_profile).default_camera or "camera"
    hints = [f"Bind the benchmark default camera '{camera_name}' through ControllerAgent.from_robot(...)."]
    if benchmark in {"obstacle-avoidance", "waypoint-nav"}:
        if robot_profile == "monsterborg-4wd":
            hints.append("Bind front_range, imu, left_encoder, and right_encoder in the controller setup block.")
            hints.append("Map all four drive motors onto logical left/right drive channels in the control policy.")
        else:
            hints.append("Bind ps0-ps7 through getDevice(...) in the controller setup block.")
    return sorted(dict.fromkeys(hints if result_reason != "completed" else []))


def resolve_example_controller(scenario: str, *, robot_profile: str = "e-puck") -> str:
    return str(get_scenario(scenario, robot_profile=robot_profile).controller)
