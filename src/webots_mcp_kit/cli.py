from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import __version__
from .benchmark import format_benchmark_report, list_benchmarks, run_benchmark
from .benchmarks import scenario_names
from .controller_authoring import edit_controller, format_controller_edit_report, format_controller_inspection_report, inspect_controller
from .controller_scaffold import scaffold_controller
from .controller_validation import format_validation_report, validate_controller
from .doctor import format_doctor_report, run_doctor
from .launcher import inspect_session, start_session
from .mcp_server import run as run_mcp_server
from .session_ops import read_session_log, session_log_paths, stop_session_json
from .scenario_ops import (
    build_scenario,
    describe_scenario,
    export_session,
    format_scenario_doctor_report,
    format_scenario_validation_report,
    format_session_replay,
    import_project,
    init_project,
    init_scenario,
    replay_session,
    scenario_doctor,
    validate_scenario,
)
from .world_ops import edit_world, format_world_edit, format_world_inspection, format_world_validation, inspect_world, validate_world


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="webots-kit")
    parser.add_argument("--version", action="version", version=f"webots-mcp-kit {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor = subparsers.add_parser("doctor")
    doctor.add_argument("--json", action="store_true")

    session_parser = subparsers.add_parser("session")
    session_sub = session_parser.add_subparsers(dest="session_command", required=True)
    start = session_sub.add_parser("start")
    start.add_argument("--scenario", choices=scenario_names(), default="line-follower")
    start.add_argument("--world")
    start.add_argument("--controller", default="example")
    start.add_argument("--robot-profile")
    start.add_argument("--robot-name")
    start.add_argument("--robot-def")
    start.add_argument("--mode", choices=["fast", "realtime", "pause"], default="fast")
    start.add_argument("--render", choices=["on", "off"], default="off")
    stop = session_sub.add_parser("stop")
    stop.add_argument("--session", required=True)
    inspect = session_sub.add_parser("inspect")
    inspect.add_argument("--session", required=True)
    logs = session_sub.add_parser("logs")
    logs.add_argument("--session", required=True)
    logs.add_argument("--name")
    logs.add_argument("--tail", type=int, default=40)
    export = session_sub.add_parser("export")
    export.add_argument("session")
    export.add_argument("--output")
    replay = session_sub.add_parser("replay")
    replay.add_argument("path")
    replay.add_argument("--json", action="store_true")

    benchmark = subparsers.add_parser("benchmark")
    benchmark_sub = benchmark.add_subparsers(dest="benchmark_command", required=True)
    benchmark_sub.add_parser("list")
    benchmark_run = benchmark_sub.add_parser("run")
    benchmark_run.add_argument("benchmark_name", choices=scenario_names())
    benchmark_run.add_argument("--controller", default="example")
    benchmark_run.add_argument("--output", required=True)
    benchmark_run.add_argument("--robot-profile")
    benchmark_run.add_argument("--duration-s", type=float, default=20.0)
    benchmark_run.add_argument("--world")
    benchmark_run.add_argument("--robot-name")
    benchmark_run.add_argument("--robot-def")
    benchmark_report = benchmark_sub.add_parser("report")
    benchmark_report.add_argument("report_path")

    controller = subparsers.add_parser("controller")
    controller_sub = controller.add_subparsers(dest="controller_command", required=True)
    validate = controller_sub.add_parser("validate")
    validate.add_argument("path")
    validate.add_argument("--scenario", choices=scenario_names())
    validate.add_argument("--spec")
    validate.add_argument("--robot-profile")
    validate.add_argument("--strict", action="store_true")
    validate.add_argument("--json", action="store_true")
    scaffold = controller_sub.add_parser("scaffold")
    scaffold.add_argument("path")
    scaffold.add_argument("--scenario", choices=scenario_names(), default="line-follower")
    scaffold.add_argument("--language", choices=["python", "cpp"], default="python")
    scaffold.add_argument("--spec")
    scaffold.add_argument("--world")
    scaffold.add_argument("--robot-profile")
    scaffold.add_argument("--robot-name")
    scaffold.add_argument("--robot-def")
    scaffold.add_argument("--force", action="store_true")
    inspect_controller_parser = controller_sub.add_parser("inspect")
    inspect_controller_parser.add_argument("path")
    inspect_controller_parser.add_argument("--scenario", choices=scenario_names())
    inspect_controller_parser.add_argument("--spec")
    inspect_controller_parser.add_argument("--robot-profile")
    inspect_controller_parser.add_argument("--json", action="store_true")
    edit_controller_parser = controller_sub.add_parser("edit")
    edit_controller_parser.add_argument("path")
    edit_controller_parser.add_argument("--plan", required=True)
    edit_controller_parser.add_argument("--robot-profile")
    edit_controller_parser.add_argument("--json", action="store_true")

    project = subparsers.add_parser("project")
    project_sub = project.add_subparsers(dest="project_command", required=True)
    project_init = project_sub.add_parser("init")
    project_init.add_argument("path")
    project_init.add_argument("--name")
    project_init.add_argument("--force", action="store_true")
    project_import = project_sub.add_parser("import")
    project_import.add_argument("--world", required=True)
    project_import.add_argument("--controller", required=True)
    project_import.add_argument("--project-root")

    scenario = subparsers.add_parser("scenario")
    scenario_sub = scenario.add_subparsers(dest="scenario_command", required=True)
    scenario_init = scenario_sub.add_parser("init")
    scenario_init.add_argument("path")
    scenario_init.add_argument("--template", required=True)
    scenario_init.add_argument("--force", action="store_true")
    scenario_validate = scenario_sub.add_parser("validate")
    scenario_validate.add_argument("spec_path")
    scenario_validate.add_argument("--json", action="store_true")
    scenario_build = scenario_sub.add_parser("build")
    scenario_build.add_argument("spec_path")
    scenario_build.add_argument("--force", action="store_true")
    scenario_describe = scenario_sub.add_parser("describe")
    scenario_describe.add_argument("spec_path")
    scenario_doctor_parser = scenario_sub.add_parser("doctor")
    scenario_doctor_parser.add_argument("spec_path")
    scenario_doctor_parser.add_argument("--json", action="store_true")

    mcp_parser = subparsers.add_parser("mcp")
    mcp_sub = mcp_parser.add_subparsers(dest="mcp_command", required=True)
    mcp_sub.add_parser("serve")

    world_parser = subparsers.add_parser("world")
    world_sub = world_parser.add_subparsers(dest="world_command", required=True)
    world_inspect = world_sub.add_parser("inspect")
    world_inspect.add_argument("path")
    world_inspect.add_argument("--json", action="store_true")
    world_validate_parser = world_sub.add_parser("validate")
    world_validate_parser.add_argument("path")
    world_validate_parser.add_argument("--json", action="store_true")
    world_edit_parser = world_sub.add_parser("edit")
    world_edit_parser.add_argument("path")
    world_edit_parser.add_argument("--plan", required=True)
    world_edit_parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "doctor":
        report = run_doctor()
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            print(format_doctor_report(report))
        return

    if args.command == "session":
        if args.session_command == "start":
            manifest = start_session(
                world=args.world,
                controller=args.controller,
                mode=args.mode,
                render=args.render == "on",
                scenario=args.scenario,
                robot_profile=args.robot_profile,
                robot_name=args.robot_name,
                robot_def=args.robot_def,
            )
            print(json.dumps(manifest.to_dict(), indent=2))
            return
        if args.session_command == "stop":
            print(stop_session_json(args.session))
            return
        if args.session_command == "inspect":
            print(json.dumps(inspect_session(args.session), indent=2))
            return
        if args.session_command == "logs":
            if args.name:
                print(read_session_log(args.session, args.name, args.tail))
            else:
                print(json.dumps(session_log_paths(args.session), indent=2))
            return
        if args.session_command == "export":
            print(json.dumps(export_session(args.session, output=Path(args.output) if args.output else None).to_dict(), indent=2))
            return
        if args.session_command == "replay":
            payload = replay_session(Path(args.path))
            if args.json:
                print(json.dumps(payload, indent=2))
            else:
                print(format_session_replay(payload))
            return

    if args.command == "benchmark":
        if args.benchmark_command == "list":
            print(json.dumps(list_benchmarks(), indent=2))
            return
        if args.benchmark_command == "run":
            report = run_benchmark(
                scenario=args.benchmark_name,
                controller=args.controller,
                output=Path(args.output),
                robot_profile=args.robot_profile,
                duration_s=args.duration_s,
                world=args.world,
                robot_name=args.robot_name,
                robot_def=args.robot_def,
            )
            print(json.dumps(report.to_dict(), indent=2))
            return
        if args.benchmark_command == "report":
            print(format_benchmark_report(Path(args.report_path)))
            return

    if args.command == "controller" and args.controller_command == "validate":
        result = validate_controller(
            Path(args.path),
            scenario=args.scenario,
            strict=args.strict,
            spec_path=Path(args.spec) if getattr(args, "spec", None) else None,
            robot_profile=getattr(args, "robot_profile", None),
        )
        if args.json:
            print(json.dumps(result.to_dict(), indent=2))
        else:
            print(format_validation_report(result))
        return
    if args.command == "controller" and args.controller_command == "scaffold":
        print(
            json.dumps(
                scaffold_controller(
                    path=Path(args.path),
                    scenario=args.scenario,
                    force=args.force,
                    language=args.language,
                    spec_path=Path(args.spec) if args.spec else None,
                    world=Path(args.world) if args.world else None,
                    robot_profile=args.robot_profile,
                    robot_name=args.robot_name,
                    robot_def=args.robot_def,
                ),
                indent=2,
            )
        )
        return
    if args.command == "controller" and args.controller_command == "inspect":
        payload = inspect_controller(
            Path(args.path),
            scenario=args.scenario,
            spec_path=Path(args.spec) if getattr(args, "spec", None) else None,
            robot_profile=getattr(args, "robot_profile", None),
        )
        if args.json:
            print(json.dumps(payload.to_dict(), indent=2))
        else:
            print(format_controller_inspection_report(payload))
        return
    if args.command == "controller" and args.controller_command == "edit":
        payload = edit_controller(Path(args.path), plan_path=Path(args.plan), robot_profile=getattr(args, "robot_profile", None))
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print(format_controller_edit_report(payload))
        return

    if args.command == "project" and args.project_command == "init":
        print(json.dumps(init_project(Path(args.path), name=args.name, force=args.force), indent=2))
        return
    if args.command == "project" and args.project_command == "import":
        print(
            json.dumps(
                import_project(
                    world=Path(args.world),
                    controller=Path(args.controller),
                    project_root=Path(args.project_root) if args.project_root else None,
                ),
                indent=2,
            )
        )
        return

    if args.command == "scenario" and args.scenario_command == "init":
        print(json.dumps(init_scenario(Path(args.path), template=args.template, force=args.force), indent=2))
        return
    if args.command == "scenario" and args.scenario_command == "validate":
        payload = validate_scenario(Path(args.spec_path))
        if args.json:
            print(json.dumps(payload.to_dict(), indent=2))
        else:
            print(format_scenario_validation_report(payload))
        return
    if args.command == "scenario" and args.scenario_command == "build":
        print(json.dumps(build_scenario(Path(args.spec_path), force=args.force).to_dict(), indent=2))
        return
    if args.command == "scenario" and args.scenario_command == "describe":
        print(describe_scenario(Path(args.spec_path)))
        return
    if args.command == "scenario" and args.scenario_command == "doctor":
        payload = scenario_doctor(Path(args.spec_path))
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print(format_scenario_doctor_report(payload))
        return

    if args.command == "mcp" and args.mcp_command == "serve":
        run_mcp_server()
        return

    if args.command == "world" and args.world_command == "inspect":
        payload = inspect_world(Path(args.path))
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print(format_world_inspection(payload))
        return
    if args.command == "world" and args.world_command == "validate":
        payload = validate_world(Path(args.path))
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print(format_world_validation(payload))
        return
    if args.command == "world" and args.world_command == "edit":
        payload = edit_world(Path(args.path), plan_path=Path(args.plan))
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print(format_world_edit(payload))
        return


if __name__ == "__main__":
    main()
