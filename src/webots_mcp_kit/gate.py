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
    generated_project = root / "generated-project"
    plans_dir = root / "plans"
    generated_cases = [
        {
            "name": "generated_line",
            "dir": generated_project / "scenarios" / "demo-line",
            "template": "epuck-line-track",
            "benchmark": "line-follower",
            "world": generated_project / "scenarios" / "demo-line" / "worlds" / "demo-line.wbt",
            "controller": generated_project / "scenarios" / "demo-line" / "controllers" / "demo-line_agent.py",
            "robot_name": "epuck-demo-line-line-follow",
            "duration_s": "3",
        },
        {
            "name": "generated_waypoint",
            "dir": generated_project / "scenarios" / "demo-waypoint",
            "template": "epuck-waypoint",
            "benchmark": "waypoint-nav",
            "world": generated_project / "scenarios" / "demo-waypoint" / "worlds" / "demo-waypoint.wbt",
            "controller": generated_project / "scenarios" / "demo-waypoint" / "controllers" / "demo-waypoint_agent.py",
            "robot_name": "epuck-demo-waypoint-waypoint-nav",
            "duration_s": "5",
        },
        {
            "name": "generated_obstacle",
            "dir": generated_project / "scenarios" / "demo-obstacle",
            "template": "epuck-obstacle-course",
            "benchmark": "obstacle-avoidance",
            "world": generated_project / "scenarios" / "demo-obstacle" / "worlds" / "demo-obstacle.wbt",
            "controller": generated_project / "scenarios" / "demo-obstacle" / "controllers" / "demo-obstacle_agent.py",
            "robot_name": "epuck-demo-obstacle-obstacle-avoidance",
            "duration_s": "5",
        },
    ]
    bundle_root = bundled_example_root()
    import_world = bundle_root / "line-follower" / "worlds" / "line_follower_benchmark.wbt"
    import_controller = bundle_root / "line-follower" / "controllers" / "line_follower_agent.py"
    import_project_root = root / "imported-project"
    imported_export = root / "exports" / "imported-line"
    imported_world_copy = root / "editable-imported-line.wbt"
    generated_waypoint_plan = plans_dir / "generated-waypoint-world-edit.json"
    imported_world_plan = plans_dir / "imported-world-edit.json"

    steps: list[GateStep] = [
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
        GateStep(
            "import_project",
            ("project", "import", "--world", str(imported_world_copy), "--controller", str(import_controller), "--project-root", str(import_project_root)),
        ),
        GateStep("imported_world_inspect", ("world", "inspect", str(imported_world_copy), "--json")),
        GateStep("imported_world_validate", ("world", "validate", str(imported_world_copy), "--json")),
        GateStep("imported_world_edit", ("world", "edit", str(imported_world_copy), "--plan", str(imported_world_plan))),
        GateStep("imported_session_start", ("session", "start", "--scenario", "line-follower", "--world", str(imported_world_copy), "--controller", str(import_controller), "--mode", "fast", "--render", "off")),
        GateStep("imported_session_inspect", ("session", "inspect", "--session", "{imported_session_id}")),
        GateStep("imported_session_stop", ("session", "stop", "--session", "{imported_session_id}")),
        GateStep("imported_session_export", ("session", "export", "{imported_session_id}", "--output", str(imported_export))),
        GateStep("imported_session_replay", ("session", "replay", str(imported_export))),
        GateStep("imported_session_replay_manifest", ("session", "replay", str(imported_export / "export.json"))),
    ]
    generated_steps: list[GateStep] = []
    for case in generated_cases:
        spec_path = case["dir"] / "webots-kit.scenario.json"
        report_path = reports_dir / f"{case['name']}-report.json"
        session_token = "{" + f"{case['name']}_session_id" + "}"
        generated_steps.extend(
            [
                GateStep(f"{case['name']}_scenario_init", ("scenario", "init", str(case["dir"]), "--template", str(case["template"]), "--force")),
                GateStep(f"{case['name']}_scenario_enrich", (str(spec_path),)),
                GateStep(f"{case['name']}_scenario_validate", ("scenario", "validate", str(spec_path))),
                GateStep(f"{case['name']}_scenario_build", ("scenario", "build", str(spec_path), "--force")),
                *(
                    [
                        GateStep(f"{case['name']}_world_inspect", ("world", "inspect", str(case["world"]), "--json")),
                        GateStep(f"{case['name']}_world_validate", ("world", "validate", str(case["world"]), "--json")),
                        GateStep(f"{case['name']}_world_edit", ("world", "edit", str(case["world"]), "--plan", str(generated_waypoint_plan))),
                    ]
                    if case["name"] == "generated_waypoint"
                    else []
                ),
                GateStep(
                    f"{case['name']}_session_start",
                    (
                        "session",
                        "start",
                        "--scenario",
                        str(case["benchmark"]),
                        "--world",
                        str(case["world"]),
                        "--controller",
                        str(case["controller"]),
                        "--robot-name",
                        str(case["robot_name"]),
                        "--robot-def",
                        "EPUCK",
                        "--mode",
                        "fast",
                        "--render",
                        "off",
                    ),
                ),
                GateStep(f"{case['name']}_session_stop", ("session", "stop", "--session", session_token)),
                GateStep(
                    f"{case['name']}_benchmark_run",
                    (
                        "benchmark",
                        "run",
                        str(case["benchmark"]),
                        "--controller",
                        str(case["controller"]),
                        "--world",
                        str(case["world"]),
                        "--robot-name",
                        str(case["robot_name"]),
                        "--robot-def",
                        "EPUCK",
                        "--output",
                        str(report_path),
                        "--duration-s",
                        str(case["duration_s"]),
                    ),
                ),
            ]
        )
    insert_at = steps.index(next(step for step in steps if step.name == "import_project"))
    return [*steps[:insert_at], *generated_steps, *steps[insert_at:]]
