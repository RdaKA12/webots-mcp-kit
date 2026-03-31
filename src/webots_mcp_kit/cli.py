from __future__ import annotations

import argparse
import json
from pathlib import Path

from .benchmark import format_benchmark_report, list_benchmarks, run_benchmark
from .benchmarks import scenario_names
from .controller_scaffold import scaffold_controller
from .controller_validation import format_validation_report, validate_controller
from .doctor import format_doctor_report, run_doctor
from .launcher import inspect_session, start_session
from .mcp_server import run as run_mcp_server
from .session_ops import read_session_log, session_log_paths, stop_session_json


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="webots-kit")
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor = subparsers.add_parser("doctor")
    doctor.add_argument("--json", action="store_true")

    session_parser = subparsers.add_parser("session")
    session_sub = session_parser.add_subparsers(dest="session_command", required=True)
    start = session_sub.add_parser("start")
    start.add_argument("--scenario", choices=scenario_names(), default="line-follower")
    start.add_argument("--world")
    start.add_argument("--controller", default="example")
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

    benchmark = subparsers.add_parser("benchmark")
    benchmark_sub = benchmark.add_subparsers(dest="benchmark_command", required=True)
    benchmark_sub.add_parser("list")
    benchmark_run = benchmark_sub.add_parser("run")
    benchmark_run.add_argument("benchmark_name", choices=scenario_names())
    benchmark_run.add_argument("--controller", default="example")
    benchmark_run.add_argument("--output", required=True)
    benchmark_run.add_argument("--duration-s", type=float, default=20.0)
    benchmark_report = benchmark_sub.add_parser("report")
    benchmark_report.add_argument("report_path")

    controller = subparsers.add_parser("controller")
    controller_sub = controller.add_subparsers(dest="controller_command", required=True)
    validate = controller_sub.add_parser("validate")
    validate.add_argument("path")
    validate.add_argument("--scenario", choices=scenario_names())
    validate.add_argument("--strict", action="store_true")
    validate.add_argument("--json", action="store_true")
    scaffold = controller_sub.add_parser("scaffold")
    scaffold.add_argument("path")
    scaffold.add_argument("--scenario", choices=scenario_names(), default="line-follower")
    scaffold.add_argument("--force", action="store_true")

    mcp_parser = subparsers.add_parser("mcp")
    mcp_sub = mcp_parser.add_subparsers(dest="mcp_command", required=True)
    mcp_sub.add_parser("serve")
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

    if args.command == "benchmark":
        if args.benchmark_command == "list":
            print(json.dumps(list_benchmarks(), indent=2))
            return
        if args.benchmark_command == "run":
            report = run_benchmark(
                scenario=args.benchmark_name,
                controller=args.controller,
                output=Path(args.output),
                duration_s=args.duration_s,
            )
            print(json.dumps(report.to_dict(), indent=2))
            return
        if args.benchmark_command == "report":
            print(format_benchmark_report(Path(args.report_path)))
            return

    if args.command == "controller" and args.controller_command == "validate":
        result = validate_controller(Path(args.path), scenario=args.scenario, strict=args.strict)
        if args.json:
            print(json.dumps(result.to_dict(), indent=2))
        else:
            print(format_validation_report(result))
        return
    if args.command == "controller" and args.controller_command == "scaffold":
        print(json.dumps(scaffold_controller(path=Path(args.path), scenario=args.scenario, force=args.force), indent=2))
        return

    if args.command == "mcp" and args.mcp_command == "serve":
        run_mcp_server()


if __name__ == "__main__":
    main()
