from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from webots_mcp_kit import mcp_server
from webots_mcp_kit.models import bundled_example_root


RUN_SMOKE = os.environ.get("WEBOTS_KIT_RUN_SMOKE") == "1"
RUN_RUNTIME_SMOKE = os.environ.get("WEBOTS_KIT_RUN_RUNTIME_SMOKE") == "1"
REPO_ROOT = Path(__file__).resolve().parents[1]
GENERATED_SCENARIO_CASES = [
    ("epuck-line-track", "demo-line", "line-follower", 3),
    ("epuck-waypoint", "demo-waypoint", "waypoint-nav", 5),
    ("epuck-obstacle-course", "demo-obstacle", "obstacle-avoidance", 5),
]


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


def run_diagnostics(*args: str, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        [sys.executable, "-m", "webots_mcp_kit.diagnostics", *args],
        cwd=str(REPO_ROOT),
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=timeout,
        check=True,
    )


def wait_for_camera_capture(session_id: str, path: Path, *, attempts: int = 3, delay_s: float = 1.0) -> dict[str, object]:
    last_payload: dict[str, object] | None = None
    for _ in range(attempts):
        payload = mcp_server.webots_capture_camera(session=session_id, path=str(path))
        if isinstance(payload.get("path"), str):
            return payload
        last_payload = payload
        time.sleep(delay_s)
    raise AssertionError(f"Camera capture did not succeed for session {session_id}: {last_payload}")


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
@pytest.mark.parametrize(("template", "scenario_name", "expected_benchmark", "duration_s"), GENERATED_SCENARIO_CASES)
def test_generated_scenario_smoke(tmp_path: Path, template: str, scenario_name: str, expected_benchmark: str, duration_s: int) -> None:
    project_root = tmp_path / "generated-project"
    run_cli("project", "init", str(project_root))
    scenario_dir = project_root / "scenarios" / scenario_name
    run_cli("scenario", "init", str(scenario_dir), "--template", template)
    validation = run_cli("scenario", "validate", str(scenario_dir / "webots-kit.scenario.json"), "--json")
    validation_payload = json.loads(validation.stdout)
    assert validation_payload["valid"] is True

    built = run_cli("scenario", "build", str(scenario_dir / "webots-kit.scenario.json"))
    generated = json.loads(built.stdout)
    assert generated["benchmark_name"] == expected_benchmark
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
        str(duration_s),
        timeout=240,
    )
    payload = json.loads(benchmark.stdout)
    assert payload["benchmark"] == generated["benchmark_name"]
    assert report_path.exists()


@pytest.mark.skipif(not RUN_RUNTIME_SMOKE, reason="Runtime smoke tests are disabled unless WEBOTS_KIT_RUN_RUNTIME_SMOKE=1.")
def test_imported_project_smoke(tmp_path: Path) -> None:
    project_root = tmp_path / "imported-project"
    examples_root = bundled_example_root()
    world = examples_root / "line-follower" / "worlds" / "line_follower_benchmark.wbt"
    controller = examples_root / "line-follower" / "controllers" / "line_follower_agent.py"

    imported = run_cli("project", "import", "--world", str(world), "--controller", str(controller), "--project-root", str(project_root))
    payload = json.loads(imported.stdout)
    spec_path = Path(payload["scenario_metadata_path"])
    assert spec_path.exists()

    validation = run_cli("scenario", "validate", str(spec_path), "--json")
    validation_payload = json.loads(validation.stdout)
    assert validation_payload["valid"] is True

    started = run_cli(
        "session",
        "start",
        "--scenario",
        "line-follower",
        "--world",
        str(world),
        "--controller",
        str(controller),
        "--mode",
        "fast",
        "--render",
        "off",
        timeout=180,
    )
    manifest = json.loads(started.stdout)
    assert manifest["status"] == "ready"
    inspected = run_cli("session", "inspect", "--session", manifest["session_id"])
    inspect_payload = json.loads(inspected.stdout)
    assert inspect_payload["session_state"]["scenario"] == "line-follower"
    stopped = run_cli("session", "stop", "--session", manifest["session_id"], timeout=60)
    stopped_manifest = json.loads(stopped.stdout)
    assert stopped_manifest["status"] in {"stopped", "failed"}


@pytest.mark.skipif(not RUN_RUNTIME_SMOKE, reason="Runtime smoke tests are disabled unless WEBOTS_KIT_RUN_RUNTIME_SMOKE=1.")
def test_mcp_contract_smoke(tmp_path: Path) -> None:
    report_path = tmp_path / "mcp-benchmark-report.json"
    start_payload = mcp_server.webots_session_start(scenario="line-follower", controller="example", mode="fast", render=False)
    session_id = str(start_payload["session_id"])
    try:
        state_payload = mcp_server.webots_get_state(session=session_id)
        devices_payload = mcp_server.webots_list_devices(session=session_id)
        sensors_payload = mcp_server.webots_get_sensors(session=session_id)
        capture_payload = wait_for_camera_capture(session_id, tmp_path / "mcp-capture.ppm")
    finally:
        stop_payload = mcp_server.webots_session_stop(session=session_id)

    benchmark_payload = mcp_server.webots_run_benchmark(
        scenario="line-follower",
        controller="example",
        duration_s=3.0,
        output=str(report_path),
    )

    assert start_payload["status"] == "ready"
    assert start_payload["environment"]["webots_version"] == "R2025a"
    assert state_payload["session"]["session_id"] == session_id
    assert isinstance(state_payload["session_state"], dict)
    assert isinstance(devices_payload["devices"], list)
    assert devices_payload["robot"]
    assert isinstance(sensors_payload["metrics"], dict)
    assert isinstance(sensors_payload["state"], dict)
    assert capture_payload["path"] == str(tmp_path / "mcp-capture.ppm")
    assert stop_payload["status"] in {"stopping", "stopped", "failed"}
    assert benchmark_payload["benchmark"] == "line-follower"
    assert isinstance(benchmark_payload["artifacts"], dict)
    assert isinstance(benchmark_payload["notes"], list)
    assert isinstance(benchmark_payload["extra_metrics"], dict)
    assert report_path.exists()


@pytest.mark.skipif(not RUN_RUNTIME_SMOKE, reason="Runtime smoke tests are disabled unless WEBOTS_KIT_RUN_RUNTIME_SMOKE=1.")
def test_session_export_replay_diagnostics_smoke(tmp_path: Path) -> None:
    diagnostics_dir = tmp_path / "diagnostics"
    export_dir = tmp_path / "export"
    started = run_cli("session", "start", "--scenario", "line-follower", "--controller", "example", "--mode", "fast", "--render", "off")
    manifest = json.loads(started.stdout)
    session_id = manifest["session_id"]
    run_cli("session", "stop", "--session", session_id, timeout=60)

    diagnostics = run_diagnostics("--output", str(diagnostics_dir), "--session", session_id, timeout=120)
    diagnostics_payload = json.loads(diagnostics.stdout)
    exported = run_cli("session", "export", session_id, "--output", str(export_dir), timeout=120)
    export_payload = json.loads(exported.stdout)
    replayed = run_cli("session", "replay", str(export_dir / "export.json"), "--json", timeout=120)
    replay_payload = json.loads(replayed.stdout)

    assert diagnostics_payload["session_id"] == session_id
    assert (diagnostics_dir / "doctor.json").exists()
    assert (diagnostics_dir / "session.json").exists()
    assert (diagnostics_dir / "inspect.json").exists()
    assert (diagnostics_dir / "log_inventory.json").exists()
    assert (diagnostics_dir / "log_summary.json").exists()
    assert (diagnostics_dir / "runtime_environment.json").exists()
    assert (diagnostics_dir / "summary.json").exists()
    assert Path(export_payload["export_manifest_path"]).exists()
    assert replay_payload["session_id"] == session_id
    assert replay_payload["artifact_standard_version"] == 1
    assert replay_payload["replay_mode"] == "observability"


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
