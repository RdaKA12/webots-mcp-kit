from __future__ import annotations

import json
from pathlib import Path

from .benchmarks import get_scenario, scenario_registry
from .client import SessionClient
from .launcher import start_session
from .models import BenchmarkReport


def list_benchmarks() -> list[dict[str, str]]:
    return [
        {"name": scenario.name, "description": scenario.description}
        for scenario in scenario_registry().values()
    ]


def run_benchmark(
    *,
    scenario: str,
    controller: str | None,
    output: Path,
    duration_s: float = 20.0,
) -> BenchmarkReport:
    session = start_session(world=None, controller=controller, mode="fast", render=False, scenario=scenario)
    client = SessionClient(session)
    try:
        result = client.request(
            "run_benchmark",
            {
                "benchmark": scenario,
                "duration_s": duration_s,
                "line_loss_streak_fail": 25,
            },
            timeout=max(duration_s + 20.0, 45.0),
        )
        report = BenchmarkReport(
            benchmark=result["benchmark"],
            world=result["world"],
            controller=result["controller"],
            session_mode=result["session_mode"],
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
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
        return report
    finally:
        try:
            client.request("stop", timeout=10.0)
        except Exception:
            pass


def run_line_follower_benchmark(*, controller: str | None, output: Path, duration_s: float = 20.0) -> BenchmarkReport:
    return run_benchmark(scenario="line-follower", controller=controller, output=output, duration_s=duration_s)


def format_benchmark_report(path: Path) -> str:
    data = json.loads(path.read_text(encoding="utf-8"))
    lines = [
        f"benchmark: {data['benchmark']}",
        f"world: {data['world']}",
        f"controller: {data['controller']}",
        f"session_mode: {data['session_mode']}",
        f"sim_time_s: {data['sim_time_s']}",
        f"steps: {data['steps']}",
        f"line_loss_events: {data['line_loss_events']}",
        f"max_line_loss_streak: {data['max_line_loss_streak']}",
        f"mean_center_error: {data['mean_center_error']}",
        f"ir_balance_error: {data['ir_balance_error']}",
        f"pass: {data['pass']}",
        f"artifacts: {data['artifacts']}",
        f"notes: {data['notes']}",
    ]
    extra_metrics = data.get("extra_metrics", {})
    if extra_metrics:
        lines.append(f"extra_metrics: {extra_metrics}")
    return "\n".join(lines)


def resolve_example_controller(scenario: str) -> str:
    return str(get_scenario(scenario).controller)
