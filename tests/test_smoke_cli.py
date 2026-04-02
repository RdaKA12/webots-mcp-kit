from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


RUN_SMOKE = os.environ.get("WEBOTS_KIT_RUN_SMOKE") == "1"
RUN_RUNTIME_SMOKE = os.environ.get("WEBOTS_KIT_RUN_RUNTIME_SMOKE") == "1"
REPO_ROOT = Path(__file__).resolve().parents[1]


def run_cli(*args: str, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        [sys.executable, "-m", "webots_mcp_kit.cli", *args],
        cwd=str(REPO_ROOT),
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=timeout,
        check=True,
    )


@pytest.mark.skipif(not RUN_RUNTIME_SMOKE, reason="Runtime smoke tests are disabled unless WEBOTS_KIT_RUN_RUNTIME_SMOKE=1.")
def test_session_start_inspect_stop_smoke() -> None:
    started = run_cli("session", "start", "--scenario", "line-follower", "--controller", "example", "--mode", "fast", "--render", "off")
    manifest = json.loads(started.stdout)
    inspected = run_cli("session", "inspect", "--session", manifest["session_id"])
    payload = json.loads(inspected.stdout)
    assert payload["manifest"]["status"] in {"ready", "stopping", "stopped"}
    stopped = run_cli("session", "stop", "--session", manifest["session_id"])
    stopped_manifest = json.loads(stopped.stdout)
    assert stopped_manifest["status"] in {"stopped", "failed"}


@pytest.mark.skipif(not RUN_RUNTIME_SMOKE, reason="Runtime smoke tests are disabled unless WEBOTS_KIT_RUN_RUNTIME_SMOKE=1.")
def test_benchmark_smoke() -> None:
    report_path = REPO_ROOT / "artifacts" / "ci-line-follower-report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    completed = run_cli(
        "benchmark",
        "run",
        "line-follower",
        "--controller",
        "example",
        "--output",
        str(report_path),
        "--duration-s",
        "3",
        timeout=180,
    )
    report = json.loads(completed.stdout)
    assert report["benchmark"] == "line-follower"
    assert report["pass"] is True


@pytest.mark.skipif(not RUN_RUNTIME_SMOKE, reason="Runtime smoke tests are disabled unless WEBOTS_KIT_RUN_RUNTIME_SMOKE=1.")
def test_generated_scenario_smoke(tmp_path: Path) -> None:
    project_root = tmp_path / "generated-project"
    run_cli("project", "init", str(project_root))
    scenario_dir = project_root / "scenarios" / "demo-waypoint"
    run_cli("scenario", "init", str(scenario_dir), "--template", "epuck-waypoint")
    validation = run_cli("scenario", "validate", str(scenario_dir / "webots-kit.scenario.json"), "--json")
    validation_payload = json.loads(validation.stdout)
    assert validation_payload["valid"] is True

    built = run_cli("scenario", "build", str(scenario_dir / "webots-kit.scenario.json"))
    generated = json.loads(built.stdout)
    started = run_cli(
        "session",
        "start",
        "--scenario",
        generated["benchmark_name"],
        "--world",
        generated["world_path"],
        "--controller",
        generated["controller_path"],
        "--robot-name",
        generated["target_robot_name"],
        "--robot-def",
        generated["target_robot_def"],
        "--mode",
        "fast",
        "--render",
        "off",
        timeout=180,
    )
    manifest = json.loads(started.stdout)
    assert manifest["status"] == "ready"
    run_cli("session", "stop", "--session", manifest["session_id"], timeout=60)

    report_path = project_root / "artifacts" / "generated-report.json"
    benchmark = run_cli(
        "benchmark",
        "run",
        generated["benchmark_name"],
        "--controller",
        generated["controller_path"],
        "--world",
        generated["world_path"],
        "--robot-name",
        generated["target_robot_name"],
        "--robot-def",
        generated["target_robot_def"],
        "--output",
        str(report_path),
        "--duration-s",
        "5",
        timeout=240,
    )
    payload = json.loads(benchmark.stdout)
    assert payload["benchmark"] == generated["benchmark_name"]
    assert report_path.exists()


@pytest.mark.skipif(not RUN_SMOKE, reason="Smoke tests are disabled unless WEBOTS_KIT_RUN_SMOKE=1.")
def test_mcp_tool_list_smoke() -> None:
    code = """
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main():
    params = StdioServerParameters(command='python', args=['-m', 'webots_mcp_kit.cli', 'mcp', 'serve'])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            print(len(tools.tools))

asyncio.run(main())
"""
    completed = subprocess.run(  # noqa: S603
        [sys.executable, "-c", code],
        cwd=str(REPO_ROOT),
        text=True,
        capture_output=True,
        timeout=120,
        check=True,
    )
    assert int(completed.stdout.strip().splitlines()[0]) >= 12
