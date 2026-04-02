from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .models import bundled_example_root


@dataclass(frozen=True, slots=True)
class GateStep:
    name: str
    args: tuple[str, ...]


def build_v1_gate_steps(workspace: Path) -> list[GateStep]:
    root = workspace.resolve()
    reports_dir = root / "reports"
    acceptance_workspace = root / "acceptance"
    generated_project = root / "generated-project"
    generated_scenario_dir = generated_project / "scenarios" / "demo-waypoint"
    generated_spec_path = generated_scenario_dir / "webots-kit.scenario.json"
    generated_world = generated_scenario_dir / "worlds" / "demo-waypoint.wbt"
    generated_controller = generated_scenario_dir / "controllers" / "demo-waypoint_agent.py"
    generated_report = reports_dir / "generated-waypoint-report.json"
    bundle_root = bundled_example_root()
    import_world = bundle_root / "line-follower" / "worlds" / "line_follower_benchmark.wbt"
    import_controller = bundle_root / "line-follower" / "controllers" / "line_follower_agent.py"
    import_project_root = root / "imported-project"
    imported_export = root / "exports" / "imported-line"

    return [
        GateStep("doctor", ("doctor", "--json")),
        GateStep("clean_user_acceptance", ("..\\scripts\\clean_user_acceptance.py",)),  # marker step for the runner
        GateStep("bundled_benchmark_line", ("benchmark", "run", "line-follower", "--controller", "example", "--output", str(reports_dir / "line-follower.json"), "--duration-s", "3")),
        GateStep(
            "bundled_benchmark_obstacle",
            ("benchmark", "run", "obstacle-avoidance", "--controller", "example", "--output", str(reports_dir / "obstacle-avoidance.json"), "--duration-s", "5"),
        ),
        GateStep(
            "bundled_benchmark_waypoint",
            ("benchmark", "run", "waypoint-nav", "--controller", "example", "--output", str(reports_dir / "waypoint-nav.json"), "--duration-s", "20"),
        ),
        GateStep("generated_project_init", ("project", "init", str(generated_project), "--force")),
        GateStep("generated_scenario_init", ("scenario", "init", str(generated_scenario_dir), "--template", "epuck-waypoint", "--force")),
        GateStep("generated_scenario_validate", ("scenario", "validate", str(generated_spec_path))),
        GateStep("generated_scenario_build", ("scenario", "build", str(generated_spec_path), "--force")),
        GateStep(
            "generated_session_start",
            (
                "session",
                "start",
                "--scenario",
                "waypoint-nav",
                "--world",
                str(generated_world),
                "--controller",
                str(generated_controller),
                "--robot-name",
                "epuck-demo-waypoint-waypoint-nav",
                "--robot-def",
                "EPUCK",
                "--mode",
                "fast",
                "--render",
                "off",
            ),
        ),
        GateStep("generated_session_inspect", ("session", "inspect", "--session", "{generated_session_id}")),
        GateStep("generated_session_stop", ("session", "stop", "--session", "{generated_session_id}")),
        GateStep(
            "generated_benchmark_run",
            (
                "benchmark",
                "run",
                "waypoint-nav",
                "--controller",
                str(generated_controller),
                "--world",
                str(generated_world),
                "--robot-name",
                "epuck-demo-waypoint-waypoint-nav",
                "--robot-def",
                "EPUCK",
                "--output",
                str(generated_report),
                "--duration-s",
                "5",
            ),
        ),
        GateStep(
            "import_project",
            ("project", "import", "--world", str(import_world), "--controller", str(import_controller), "--project-root", str(import_project_root)),
        ),
        GateStep("imported_session_start", ("session", "start", "--scenario", "line-follower", "--world", str(import_world), "--controller", str(import_controller), "--mode", "fast", "--render", "off")),
        GateStep("imported_session_inspect", ("session", "inspect", "--session", "{imported_session_id}")),
        GateStep("imported_session_stop", ("session", "stop", "--session", "{imported_session_id}")),
        GateStep("imported_session_export", ("session", "export", "{imported_session_id}", "--output", str(imported_export))),
        GateStep("imported_session_replay", ("session", "replay", str(imported_export))),
        GateStep("imported_session_replay_manifest", ("session", "replay", str(imported_export / "export.json"))),
    ]
