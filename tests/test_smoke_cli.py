from __future__ import annotations

import json
import os
import shutil
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
    ("epuck-line-track", "demo-line", "line-follower", "e-puck", 3),
    ("epuck-waypoint", "demo-waypoint", "waypoint-nav", "e-puck", 5),
    ("epuck-obstacle-course", "demo-obstacle", "obstacle-avoidance", "e-puck", 5),
    ("monsterborg-line-track", "demo-monster-line", "line-follower", "monsterborg-4wd", 3),
    ("monsterborg-waypoint", "demo-monster-waypoint", "waypoint-nav", "monsterborg-4wd", 5),
    ("monsterborg-obstacle-course", "demo-monster-obstacle", "obstacle-avoidance", "monsterborg-4wd", 5),
]
MONSTERBORG_LINE_VARIANTS = ("baseline", "tight-turns", "broken-line-recovery", "low-contrast")
MONSTERBORG_ROBUSTNESS_VARIANTS = ("low-contrast", "friction-perturbation", "camera-degradation")
MONSTERBORG_OBSTACLE_VARIANTS = ("baseline", "narrow-corridor", "late-obstacle", "cluttered")
MONSTERBORG_OBSTACLE_ROBUSTNESS_VARIANTS = ("range-noise", "friction-perturbation")
MONSTERBORG_WAYPOINT_VARIANTS = ("baseline", "offset-start", "tight-waypoints", "low-clearance")
MONSTERBORG_WAYPOINT_ROBUSTNESS_VARIANTS = ("imu-drift", "friction-perturbation")


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def enrich_generated_spec(spec_path: Path, template: str) -> None:
    payload = json.loads(spec_path.read_text(encoding="utf-8"))
    layout = payload.setdefault("layout", {})
    if template == "epuck-line-track":
        layout["walls"] = [{"name": "wall-line-divider", "start": [-0.05, -0.35], "end": [-0.05, 0.28], "thickness": 0.02, "height": 0.08}]
        layout["landmarks"] = [{"name": "landmark-line-marker", "position": [0.35, 0.1], "radius": 0.04}]
        layout["zones"] = [{"name": "zone-line-buffer", "center": [0.4, -0.05], "size": [0.18, 0.18]}]
        layout["props"] = [{"name": "prop-line-prop", "position": [0.1, -0.25], "size": [0.06, 0.06, 0.06]}]
    elif template == "epuck-waypoint":
        layout["walls"] = [{"name": "wall-waypoint-divider", "start": [-0.2, -0.3], "end": [-0.2, 0.3], "thickness": 0.02, "height": 0.08}]
        layout["landmarks"] = [{"name": "landmark-waypoint-marker", "position": [0.15, -0.18], "radius": 0.04}]
        layout["zones"] = [{"name": "zone-goal-buffer", "center": [0.4, 0.0], "size": [0.22, 0.22]}]
        layout["props"] = [{"name": "prop-waypoint-prop", "position": [0.0, 0.45], "size": [0.08, 0.08, 0.08]}]
    elif template == "epuck-obstacle-course":
        layout["walls"] = [{"name": "wall-obstacle-divider", "start": [-0.55, -0.15], "end": [-0.15, -0.15], "thickness": 0.02, "height": 0.08}]
        layout["landmarks"] = [{"name": "landmark-obstacle-marker", "position": [0.55, -0.4], "radius": 0.04}]
        layout["zones"] = [{"name": "zone-obstacle-safe", "center": [0.55, -0.55], "size": [0.18, 0.18]}]
        layout["props"] = [{"name": "prop-obstacle-prop", "position": [-0.55, 0.55], "size": [0.08, 0.08, 0.08]}]
    spec_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


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


def bundled_example_paths(robot_profile: str, scenario: str) -> tuple[Path, Path]:
    examples_root = bundled_example_root()
    if robot_profile == "monsterborg-4wd":
        world_name = {
            "line-follower": "monsterborg_line_follower_benchmark.wbt",
            "obstacle-avoidance": "monsterborg_obstacle_avoidance_benchmark.wbt",
            "waypoint-nav": "monsterborg_waypoint_nav_benchmark.wbt",
        }[scenario]
        controller_name = {
            "line-follower": "monsterborg_line_follower_agent.py",
            "obstacle-avoidance": "monsterborg_obstacle_avoidance_agent.py",
            "waypoint-nav": "monsterborg_waypoint_nav_agent.py",
        }[scenario]
        base = examples_root / "monsterborg" / scenario
    else:
        world_name = {
            "line-follower": "line_follower_benchmark.wbt",
            "obstacle-avoidance": "obstacle_avoidance_benchmark.wbt",
            "waypoint-nav": "waypoint_nav_benchmark.wbt",
        }[scenario]
        controller_name = {
            "line-follower": "line_follower_agent.py",
            "obstacle-avoidance": "obstacle_avoidance_agent.py",
            "waypoint-nav": "waypoint_nav_agent.py",
        }[scenario]
        base = examples_root / scenario
    return base / "worlds" / world_name, base / "controllers" / controller_name


def bundled_monsterborg_variant_spec(variant: str) -> Path:
    examples_root = bundled_example_root()
    return examples_root / "monsterborg" / "line-follower" / "variants" / f"{variant}.webots-kit.scenario.json"


def bundled_monsterborg_task_variant_spec(task: str, variant: str) -> Path:
    examples_root = bundled_example_root()
    return examples_root / "monsterborg" / task / "variants" / f"{variant}.webots-kit.scenario.json"


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
@pytest.mark.parametrize("variant", MONSTERBORG_LINE_VARIANTS)
def test_monsterborg_line_follow_variants_repeatability_smoke(tmp_path: Path, variant: str) -> None:
    scenario_dir = tmp_path / variant
    scenario_dir.mkdir(parents=True, exist_ok=True)
    spec_path = scenario_dir / "webots-kit.scenario.json"
    shutil.copy2(bundled_monsterborg_variant_spec(variant), spec_path)

    validation = json.loads(run_cli("scenario", "validate", str(spec_path), "--json").stdout)
    assert validation["valid"] is True
    built = json.loads(run_cli("scenario", "build", str(spec_path)).stdout)

    controller_path = tmp_path / f"{variant}_agent.py"
    run_cli(
        "controller",
        "scaffold",
        str(controller_path),
        "--scenario",
        "line-follower",
        "--language",
        "python",
        "--robot-profile",
        "monsterborg-4wd",
        "--force",
    )
    validate_payload = json.loads(
        run_cli(
            "controller",
            "validate",
            str(controller_path),
            "--scenario",
            "line-follower",
            "--robot-profile",
            "monsterborg-4wd",
            "--strict",
            "--json",
        ).stdout
    )
    assert validate_payload["valid"] is True
    for attempt in range(5):
        report_path = tmp_path / f"{variant}-{attempt}.json"
        payload = json.loads(
            run_cli(
                "benchmark",
                "run",
                "line-follower",
                "--controller",
                str(controller_path),
                "--world",
                built["world_path"],
                "--robot-profile",
                "monsterborg-4wd",
                "--robot-name",
                built["target_robot_name"],
                "--robot-def",
                built["target_robot_def"],
                "--output",
                str(report_path),
                "--duration-s",
                "4",
                timeout=300,
            ).stdout
        )
        assert payload["pass"] is True
        assert payload["track_variant"] == variant
        assert report_path.exists()


@pytest.mark.skipif(not RUN_RUNTIME_SMOKE, reason="Runtime smoke tests are disabled unless WEBOTS_KIT_RUN_RUNTIME_SMOKE=1.")
@pytest.mark.parametrize("variant", MONSTERBORG_ROBUSTNESS_VARIANTS)
def test_monsterborg_line_follow_robustness_smoke(tmp_path: Path, variant: str) -> None:
    scenario_dir = tmp_path / f"robust-{variant}"
    scenario_dir.mkdir(parents=True, exist_ok=True)
    spec_path = scenario_dir / "webots-kit.scenario.json"
    shutil.copy2(bundled_monsterborg_variant_spec(variant), spec_path)
    built = json.loads(run_cli("scenario", "build", str(spec_path)).stdout)
    controller_path = tmp_path / f"robust-{variant}.py"
    run_cli(
        "controller",
        "scaffold",
        str(controller_path),
        "--scenario",
        "line-follower",
        "--language",
        "python",
        "--robot-profile",
        "monsterborg-4wd",
        "--force",
    )
    report_path = tmp_path / f"robust-{variant}.json"
    payload = json.loads(
        run_cli(
            "benchmark",
            "run",
            "line-follower",
            "--controller",
            str(controller_path),
            "--world",
            built["world_path"],
            "--robot-profile",
            "monsterborg-4wd",
            "--robot-name",
            built["target_robot_name"],
            "--robot-def",
            built["target_robot_def"],
            "--output",
            str(report_path),
            "--duration-s",
            "4",
            timeout=300,
        ).stdout
    )
    assert payload["pass"] is True
    assert payload["track_variant"] == variant
    assert "camera_signal_strength_mean" in payload
    assert "oscillation_score" in payload
    assert "speed_envelope_violations" in payload


@pytest.mark.skipif(not RUN_RUNTIME_SMOKE, reason="Runtime smoke tests are disabled unless WEBOTS_KIT_RUN_RUNTIME_SMOKE=1.")
@pytest.mark.parametrize("variant", MONSTERBORG_OBSTACLE_VARIANTS)
def test_monsterborg_obstacle_variants_repeatability_smoke(tmp_path: Path, variant: str) -> None:
    scenario_dir = tmp_path / f"obstacle-{variant}"
    scenario_dir.mkdir(parents=True, exist_ok=True)
    spec_path = scenario_dir / "webots-kit.scenario.json"
    shutil.copy2(bundled_monsterborg_task_variant_spec("obstacle-avoidance", variant), spec_path)
    validation = json.loads(run_cli("scenario", "validate", str(spec_path), "--json").stdout)
    assert validation["valid"] is True
    built = json.loads(run_cli("scenario", "build", str(spec_path)).stdout)
    controller_path = tmp_path / f"obstacle-{variant}.py"
    run_cli(
        "controller",
        "scaffold",
        str(controller_path),
        "--scenario",
        "obstacle-avoidance",
        "--language",
        "python",
        "--robot-profile",
        "monsterborg-4wd",
        "--force",
    )
    validate_payload = json.loads(
        run_cli(
            "controller",
            "validate",
            str(controller_path),
            "--scenario",
            "obstacle-avoidance",
            "--robot-profile",
            "monsterborg-4wd",
            "--strict",
            "--json",
        ).stdout
    )
    assert validate_payload["valid"] is True
    for attempt in range(5):
        report_path = tmp_path / f"obstacle-{variant}-{attempt}.json"
        payload = json.loads(
            run_cli(
                "benchmark",
                "run",
                "obstacle-avoidance",
                "--controller",
                str(controller_path),
                "--world",
                built["world_path"],
                "--robot-profile",
                "monsterborg-4wd",
                "--robot-name",
                built["target_robot_name"],
                "--robot-def",
                built["target_robot_def"],
                "--output",
                str(report_path),
                "--duration-s",
                "4",
                timeout=300,
            ).stdout
        )
        assert payload["pass"] is True
        assert payload["task_variant"] == variant
        assert payload["task_quality_summary"]["collision_events"] <= 1


@pytest.mark.skipif(not RUN_RUNTIME_SMOKE, reason="Runtime smoke tests are disabled unless WEBOTS_KIT_RUN_RUNTIME_SMOKE=1.")
@pytest.mark.parametrize("variant", MONSTERBORG_OBSTACLE_ROBUSTNESS_VARIANTS)
def test_monsterborg_obstacle_robustness_smoke(tmp_path: Path, variant: str) -> None:
    scenario_dir = tmp_path / f"obstacle-robust-{variant}"
    scenario_dir.mkdir(parents=True, exist_ok=True)
    spec_path = scenario_dir / "webots-kit.scenario.json"
    shutil.copy2(bundled_monsterborg_task_variant_spec("obstacle-avoidance", variant), spec_path)
    built = json.loads(run_cli("scenario", "build", str(spec_path)).stdout)
    controller_path = tmp_path / f"obstacle-robust-{variant}.py"
    run_cli(
        "controller",
        "scaffold",
        str(controller_path),
        "--scenario",
        "obstacle-avoidance",
        "--language",
        "python",
        "--robot-profile",
        "monsterborg-4wd",
        "--force",
    )
    report_path = tmp_path / f"obstacle-robust-{variant}.json"
    payload = json.loads(
        run_cli(
            "benchmark",
            "run",
            "obstacle-avoidance",
            "--controller",
            str(controller_path),
            "--world",
            built["world_path"],
            "--robot-profile",
            "monsterborg-4wd",
            "--robot-name",
            built["target_robot_name"],
            "--robot-def",
            built["target_robot_def"],
            "--output",
            str(report_path),
            "--duration-s",
            "4",
            timeout=300,
        ).stdout
    )
    assert payload["pass"] is True
    assert payload["task_variant"] == variant
    assert "task_quality_summary" in payload


@pytest.mark.skipif(not RUN_RUNTIME_SMOKE, reason="Runtime smoke tests are disabled unless WEBOTS_KIT_RUN_RUNTIME_SMOKE=1.")
@pytest.mark.parametrize("variant", MONSTERBORG_WAYPOINT_VARIANTS)
def test_monsterborg_waypoint_variants_repeatability_smoke(tmp_path: Path, variant: str) -> None:
    scenario_dir = tmp_path / f"waypoint-{variant}"
    scenario_dir.mkdir(parents=True, exist_ok=True)
    spec_path = scenario_dir / "webots-kit.scenario.json"
    shutil.copy2(bundled_monsterborg_task_variant_spec("waypoint-nav", variant), spec_path)
    validation = json.loads(run_cli("scenario", "validate", str(spec_path), "--json").stdout)
    assert validation["valid"] is True
    built = json.loads(run_cli("scenario", "build", str(spec_path)).stdout)
    controller_path = tmp_path / f"waypoint-{variant}.py"
    run_cli(
        "controller",
        "scaffold",
        str(controller_path),
        "--scenario",
        "waypoint-nav",
        "--language",
        "python",
        "--robot-profile",
        "monsterborg-4wd",
        "--force",
    )
    validate_payload = json.loads(
        run_cli(
            "controller",
            "validate",
            str(controller_path),
            "--scenario",
            "waypoint-nav",
            "--robot-profile",
            "monsterborg-4wd",
            "--strict",
            "--json",
        ).stdout
    )
    assert validate_payload["valid"] is True
    for attempt in range(5):
        report_path = tmp_path / f"waypoint-{variant}-{attempt}.json"
        payload = json.loads(
            run_cli(
                "benchmark",
                "run",
                "waypoint-nav",
                "--controller",
                str(controller_path),
                "--world",
                built["world_path"],
                "--robot-profile",
                "monsterborg-4wd",
                "--robot-name",
                built["target_robot_name"],
                "--robot-def",
                built["target_robot_def"],
                "--output",
                str(report_path),
                "--duration-s",
                "5",
                timeout=300,
            ).stdout
        )
        assert payload["pass"] is True
        assert payload["task_variant"] == variant
        assert payload["task_quality_summary"]["progress_ratio"] >= 0.85


@pytest.mark.skipif(not RUN_RUNTIME_SMOKE, reason="Runtime smoke tests are disabled unless WEBOTS_KIT_RUN_RUNTIME_SMOKE=1.")
@pytest.mark.parametrize("variant", MONSTERBORG_WAYPOINT_ROBUSTNESS_VARIANTS)
def test_monsterborg_waypoint_robustness_smoke(tmp_path: Path, variant: str) -> None:
    scenario_dir = tmp_path / f"waypoint-robust-{variant}"
    scenario_dir.mkdir(parents=True, exist_ok=True)
    spec_path = scenario_dir / "webots-kit.scenario.json"
    shutil.copy2(bundled_monsterborg_task_variant_spec("waypoint-nav", variant), spec_path)
    built = json.loads(run_cli("scenario", "build", str(spec_path)).stdout)
    controller_path = tmp_path / f"waypoint-robust-{variant}.py"
    run_cli(
        "controller",
        "scaffold",
        str(controller_path),
        "--scenario",
        "waypoint-nav",
        "--language",
        "python",
        "--robot-profile",
        "monsterborg-4wd",
        "--force",
    )
    report_path = tmp_path / f"waypoint-robust-{variant}.json"
    payload = json.loads(
        run_cli(
            "benchmark",
            "run",
            "waypoint-nav",
            "--controller",
            str(controller_path),
            "--world",
            built["world_path"],
            "--robot-profile",
            "monsterborg-4wd",
            "--robot-name",
            built["target_robot_name"],
            "--robot-def",
            built["target_robot_def"],
            "--output",
            str(report_path),
            "--duration-s",
            "5",
            timeout=300,
        ).stdout
    )
    assert payload["pass"] is True
    assert payload["task_variant"] == variant
    assert "task_quality_summary" in payload


@pytest.mark.skipif(not RUN_RUNTIME_SMOKE, reason="Runtime smoke tests are disabled unless WEBOTS_KIT_RUN_RUNTIME_SMOKE=1.")
@pytest.mark.parametrize(("template", "scenario_name", "expected_benchmark", "expected_robot_profile", "duration_s"), GENERATED_SCENARIO_CASES)
def test_generated_scenario_smoke(
    tmp_path: Path, template: str, scenario_name: str, expected_benchmark: str, expected_robot_profile: str, duration_s: int
) -> None:
    project_root = tmp_path / "generated-project"
    run_cli("project", "init", str(project_root))
    scenario_dir = project_root / "scenarios" / scenario_name
    spec_path = scenario_dir / "webots-kit.scenario.json"
    run_cli("scenario", "init", str(scenario_dir), "--template", template)
    enrich_generated_spec(spec_path, template)
    validation = run_cli("scenario", "validate", str(spec_path), "--json")
    validation_payload = json.loads(validation.stdout)
    assert validation_payload["valid"] is True

    built = run_cli("scenario", "build", str(spec_path))
    generated = json.loads(built.stdout)
    assert generated["benchmark_name"] == expected_benchmark
    assert generated["robot_profile"] == expected_robot_profile
    started = run_cli(
        "session",
        "start",
        "--scenario",
        generated["benchmark_name"],
        "--world",
        generated["world_path"],
        "--controller",
        generated["controller_path"],
        "--robot-profile",
        generated["robot_profile"],
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
        "--robot-profile",
        generated["robot_profile"],
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
    assert payload["robot_profile"] == generated["robot_profile"]
    assert report_path.exists()


@pytest.mark.skipif(not RUN_RUNTIME_SMOKE, reason="Runtime smoke tests are disabled unless WEBOTS_KIT_RUN_RUNTIME_SMOKE=1.")
def test_generated_world_edit_smoke(tmp_path: Path) -> None:
    project_root = tmp_path / "generated-authoring-project"
    run_cli("project", "init", str(project_root))
    scenario_dir = project_root / "scenarios" / "authoring-waypoint"
    spec_path = scenario_dir / "webots-kit.scenario.json"
    run_cli("scenario", "init", str(scenario_dir), "--template", "epuck-waypoint")
    enrich_generated_spec(spec_path, "epuck-waypoint")
    built = run_cli("scenario", "build", str(spec_path))
    generated = json.loads(built.stdout)

    world_path = Path(generated["world_path"])
    plan_path = project_root / "plans" / "generated-world-edit.json"
    write_json(
        plan_path,
        {
            "schema_version": 1,
            "operations": [
                {"type": "set_spawn", "translation": [-0.6, 0.0, 0.0], "rotation_z": 0.0},
                {"type": "add_landmark", "name": "landmark-generated", "position": [0.1, 0.1], "radius": 0.04},
            ],
        },
    )

    inspect_payload = json.loads(run_cli("world", "inspect", str(world_path), "--json").stdout)
    assert inspect_payload["status"] == "ready"
    assert inspect_payload["target_robot"]["def_name"] == generated["target_robot_def"]
    assert inspect_payload["spatial_summary"]["wall_count"] == 1
    assert inspect_payload["spatial_summary"]["landmark_count"] == 1
    assert inspect_payload["spatial_summary"]["zone_count"] == 2
    assert inspect_payload["spatial_summary"]["prop_count"] == 1

    edited = json.loads(run_cli("world", "edit", str(world_path), "--plan", str(plan_path), "--json").stdout)
    assert edited["status"] == "ready"
    validation = json.loads(run_cli("world", "validate", str(world_path), "--json").stdout)
    assert validation["valid"] is True

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

    report_path = project_root / "artifacts" / "generated-authoring-report.json"
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
    benchmark_payload = json.loads(benchmark.stdout)
    assert benchmark_payload["benchmark"] == "waypoint-nav"
    assert report_path.exists()


@pytest.mark.skipif(not RUN_RUNTIME_SMOKE, reason="Runtime smoke tests are disabled unless WEBOTS_KIT_RUN_RUNTIME_SMOKE=1.")
def test_python_controller_authoring_and_edit_smoke(tmp_path: Path) -> None:
    controller_path = tmp_path / "line_agent.py"
    run_cli("controller", "scaffold", str(controller_path), "--scenario", "line-follower", "--force")
    inspect_payload = json.loads(run_cli("controller", "inspect", str(controller_path), "--scenario", "line-follower", "--json").stdout)
    assert inspect_payload["status"] == "ready"
    assert inspect_payload["function_inventory"]

    plan_path = tmp_path / "python-controller-edit.json"
    write_json(
        plan_path,
        {
            "schema_version": 1,
            "operations": [
                {"type": "set_symbol_value", "symbol": "TURN_GAIN", "value": 5},
                {"type": "add_import_or_include", "statement": "import math"},
                {"type": "remove_import_or_include", "statement": "import math"},
            ],
            "scenario_context": {"scenario": "line-follower"},
        },
    )
    edit_payload = json.loads(run_cli("controller", "edit", str(controller_path), "--plan", str(plan_path), "--json").stdout)
    assert edit_payload["status"] == "ready"
    validate_payload = json.loads(
        run_cli("controller", "validate", str(controller_path), "--scenario", "line-follower", "--strict", "--json").stdout
    )
    assert validate_payload["valid"] is True

    report_path = tmp_path / "python-controller-report.json"
    benchmark_payload = json.loads(
        run_cli(
            "benchmark",
            "run",
            "line-follower",
            "--controller",
            str(controller_path),
            "--output",
            str(report_path),
            "--duration-s",
            "3",
            timeout=240,
        ).stdout
    )
    assert benchmark_payload["benchmark"] == "line-follower"
    report_text = run_cli("benchmark", "report", str(report_path)).stdout
    assert "next_step:" in report_text


@pytest.mark.skipif(not RUN_RUNTIME_SMOKE, reason="Runtime smoke tests are disabled unless WEBOTS_KIT_RUN_RUNTIME_SMOKE=1.")
def test_cpp_controller_authoring_and_edit_smoke(tmp_path: Path) -> None:
    controller_path = tmp_path / "waypoint_agent.cpp"
    run_cli("controller", "scaffold", str(controller_path), "--scenario", "waypoint-nav", "--language", "cpp", "--force")
    inspect_payload = json.loads(run_cli("controller", "inspect", str(controller_path), "--scenario", "waypoint-nav", "--json").stdout)
    assert inspect_payload["status"] == "ready"
    assert inspect_payload["function_inventory"]

    plan_path = tmp_path / "cpp-controller-edit.json"
    write_json(
        plan_path,
        {
            "schema_version": 1,
            "language": "cpp",
            "operations": [{"type": "set_symbol_value", "symbol": "CRUISE_SPEED", "value": 4.0}],
            "scenario_context": {"scenario": "waypoint-nav"},
        },
    )
    edit_payload = json.loads(run_cli("controller", "edit", str(controller_path), "--plan", str(plan_path), "--json").stdout)
    assert edit_payload["status"] == "ready"
    validate_payload = json.loads(
        run_cli("controller", "validate", str(controller_path), "--scenario", "waypoint-nav", "--strict", "--json", timeout=240).stdout
    )
    assert validate_payload["valid"] is True

    report_path = tmp_path / "cpp-controller-report.json"
    benchmark_payload = json.loads(
        run_cli(
            "benchmark",
            "run",
            "waypoint-nav",
            "--controller",
            str(controller_path),
            "--output",
            str(report_path),
            "--duration-s",
            "5",
            timeout=360,
        ).stdout
    )
    assert benchmark_payload["benchmark"] == "waypoint-nav"
    report_text = run_cli("benchmark", "report", str(report_path)).stdout
    assert "next_step:" in report_text


@pytest.mark.skipif(not RUN_RUNTIME_SMOKE, reason="Runtime smoke tests are disabled unless WEBOTS_KIT_RUN_RUNTIME_SMOKE=1.")
@pytest.mark.parametrize(
    ("robot_profile", "scenario"),
    [
        ("e-puck", "line-follower"),
        ("monsterborg-4wd", "line-follower"),
    ],
)
def test_imported_project_smoke(tmp_path: Path, robot_profile: str, scenario: str) -> None:
    project_root = tmp_path / "imported-project"
    world, controller = bundled_example_paths(robot_profile, scenario)

    imported = run_cli("project", "import", "--world", str(world), "--controller", str(controller), "--project-root", str(project_root))
    payload = json.loads(imported.stdout)
    spec_path = Path(payload["scenario_metadata_path"])
    assert spec_path.exists()
    assert payload["suggested_benchmark_name"] == scenario
    assert payload["discovered_robot_name"]
    assert payload["discovered_robot_def"]
    assert isinstance(payload["discovered_devices"], list)
    assert payload["suggested_robot_profile"] == robot_profile

    validation = run_cli("scenario", "validate", str(spec_path), "--json")
    validation_payload = json.loads(validation.stdout)
    assert validation_payload["valid"] is True

    started = run_cli(
        "session",
        "start",
        "--scenario",
        scenario,
        "--world",
        str(world),
        "--controller",
        str(controller),
        "--robot-profile",
        robot_profile,
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
    assert inspect_payload["session_state"]["scenario"] == scenario
    stopped = run_cli("session", "stop", "--session", manifest["session_id"], timeout=60)
    stopped_manifest = json.loads(stopped.stdout)
    assert stopped_manifest["status"] in {"stopped", "failed"}


@pytest.mark.skipif(not RUN_RUNTIME_SMOKE, reason="Runtime smoke tests are disabled unless WEBOTS_KIT_RUN_RUNTIME_SMOKE=1.")
def test_imported_world_edit_smoke(tmp_path: Path) -> None:
    project_root = tmp_path / "imported-authoring-project"
    examples_root = bundled_example_root()
    source_world = examples_root / "line-follower" / "worlds" / "line_follower_benchmark.wbt"
    editable_world = tmp_path / "line_follower_editable.wbt"
    editable_world.write_text(source_world.read_text(encoding="utf-8"), encoding="utf-8")
    controller = examples_root / "line-follower" / "controllers" / "line_follower_agent.py"

    plan_path = tmp_path / "world-edit.json"
    write_json(
        plan_path,
        {
            "schema_version": 1,
            "operations": [
                {"type": "add_landmark", "name": "imported-landmark", "position": [0.0, 0.0], "radius": 0.04},
            ],
        },
    )

    imported = run_cli("project", "import", "--world", str(editable_world), "--controller", str(controller), "--project-root", str(project_root))
    payload = json.loads(imported.stdout)
    assert payload["world_inventory"]["status"] == "ready"
    assert isinstance(payload["edit_target_summary"], list)

    edited = json.loads(run_cli("world", "edit", str(editable_world), "--plan", str(plan_path), "--json").stdout)
    assert edited["status"] == "ready"
    validation = json.loads(run_cli("world", "validate", str(editable_world), "--json").stdout)
    assert validation["valid"] is True

    started = run_cli(
        "session",
        "start",
        "--scenario",
        "line-follower",
        "--world",
        str(editable_world),
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
    run_cli("session", "stop", "--session", manifest["session_id"], timeout=60)

    report_path = tmp_path / "imported-authoring-report.json"
    benchmark = run_cli(
        "benchmark",
        "run",
        "line-follower",
        "--controller",
        str(controller),
        "--world",
        str(editable_world),
        "--output",
        str(report_path),
        "--duration-s",
        "3",
        timeout=240,
    )
    benchmark_payload = json.loads(benchmark.stdout)
    assert benchmark_payload["benchmark"] == "line-follower"
    assert report_path.exists()


def test_mcp_authoring_contract_unit_smoke(tmp_path: Path) -> None:
    examples_root = bundled_example_root()
    editable_world = tmp_path / "editable_line_follower.wbt"
    editable_world.write_text(
        (examples_root / "line-follower" / "worlds" / "line_follower_benchmark.wbt").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    controller_path = tmp_path / "mcp_demo_agent.py"
    controller_plan = tmp_path / "controller-edit.json"
    world_plan = tmp_path / "world-edit.json"
    write_json(controller_plan, {"schema_version": 1, "operations": [{"type": "inject_helper_function", "code": "def preview_helper() -> float:\n    return 1.0"}]})
    write_json(world_plan, {"schema_version": 1, "operations": [{"type": "add_landmark", "name": "mcp-landmark", "position": [0.0, 0.0], "radius": 0.04}]})

    scaffold_payload = mcp_server.webots_controller_scaffold(path=str(controller_path), scenario="line-follower", language="python")
    inspect_payload = mcp_server.webots_controller_inspect(path=str(controller_path), scenario="line-follower")
    validate_payload = mcp_server.webots_controller_validate(path=str(controller_path), scenario="line-follower", strict=False)
    edit_payload = mcp_server.webots_controller_edit(path=str(controller_path), plan=str(controller_plan))
    world_inspect_payload = mcp_server.webots_world_inspect(path=str(editable_world))
    world_validate_payload = mcp_server.webots_world_validate(path=str(editable_world))
    world_edit_payload = mcp_server.webots_world_edit(path=str(editable_world), plan=str(world_plan))

    assert scaffold_payload["language"] == "python"
    assert inspect_payload["language"] == "python"
    assert validate_payload["valid"] is True
    assert "inject_helper_function" in edit_payload["applied_operations"]
    assert world_inspect_payload["status"] == "ready"
    assert world_validate_payload["valid"] is True
    assert world_edit_payload["status"] == "ready"


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
def test_mcp_authoring_contract_smoke(tmp_path: Path) -> None:
    project_root = tmp_path / "mcp-authoring-project"
    run_cli("project", "init", str(project_root))
    scenario_dir = project_root / "scenarios" / "mcp-waypoint"
    spec_path = scenario_dir / "webots-kit.scenario.json"
    run_cli("scenario", "init", str(scenario_dir), "--template", "epuck-waypoint")
    enrich_generated_spec(spec_path, "epuck-waypoint")
    generated = json.loads(run_cli("scenario", "build", str(spec_path)).stdout)

    controller_path = project_root / "controllers" / "mcp_agent.py"
    (project_root / "plans").mkdir(parents=True, exist_ok=True)
    controller_edit_plan = project_root / "plans" / "controller-edit.json"
    controller_edit_plan.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "operations": [{"type": "inject_helper_function", "code": "def preview_helper() -> float:\n    return 1.0"}],
                "scenario_context": {"scenario": "waypoint-nav"},
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    world_edit_plan = project_root / "plans" / "world-edit.json"
    write_json(
        world_edit_plan,
        {
            "schema_version": 1,
            "operations": [{"type": "add_landmark", "name": "mcp-landmark", "position": [0.1, 0.1], "radius": 0.04}],
        },
    )

    scaffold_payload = mcp_server.webots_controller_scaffold(
        path=str(controller_path),
        scenario="waypoint-nav",
        language="python",
        spec=str(spec_path),
        world=generated["world_path"],
        robot_name=generated["target_robot_name"],
        robot_def=generated["target_robot_def"],
    )
    inspect_payload = mcp_server.webots_controller_inspect(str(controller_path), scenario="waypoint-nav", spec=str(spec_path))
    validate_payload = mcp_server.webots_controller_validate(str(controller_path), scenario="waypoint-nav", strict=True, spec=str(spec_path))
    edit_payload = mcp_server.webots_controller_edit(str(controller_path), str(controller_edit_plan))
    world_inspect_payload = mcp_server.webots_world_inspect(generated["world_path"])
    world_validate_payload = mcp_server.webots_world_validate(generated["world_path"])
    world_edit_payload = mcp_server.webots_world_edit(generated["world_path"], str(world_edit_plan))

    assert scaffold_payload["language"] == "python"
    assert scaffold_payload["spec_path"] == str(spec_path)
    assert isinstance(scaffold_payload["editable_regions"], list)
    assert inspect_payload["valid_source"] is True
    assert isinstance(inspect_payload["benchmark_readiness"], dict)
    assert isinstance(validate_payload["errors"], list)
    assert "inject_helper_function" in edit_payload["applied_operations"]
    assert world_inspect_payload["status"] == "ready"
    assert isinstance(world_inspect_payload["supported_edit_targets"], list)
    assert world_validate_payload["valid"] is True
    assert world_edit_payload["status"] == "ready"
    assert isinstance(world_edit_payload["validation"], dict)


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
    assert replay_payload["benchmark_summary"]["benchmark_name"] == "line-follower"
    assert "roles" in replay_payload["telemetry_summary"]
    assert replay_payload["runtime_failure_class"] == "none"
    assert replay_payload["triage_recipe"]["focus"] == "observability"


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
