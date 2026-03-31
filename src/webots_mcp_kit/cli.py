from __future__ import annotations

import argparse
import json
from pathlib import Path

from .benchmark import format_benchmark_report, run_line_follower_benchmark
from .client import SessionClient
from .doctor import format_doctor_report, run_doctor
from .launcher import start_session
from .mcp_server import run as run_mcp_server


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="webots-kit")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("doctor")

    session_parser = subparsers.add_parser("session")
    session_sub = session_parser.add_subparsers(dest="session_command", required=True)
    start = session_sub.add_parser("start")
    start.add_argument("--world")
    start.add_argument("--controller", default="example")
    start.add_argument("--mode", choices=["fast", "realtime", "pause"], default="fast")
    start.add_argument("--render", choices=["on", "off"], default="off")
    stop = session_sub.add_parser("stop")
    stop.add_argument("--session", required=True)

    benchmark = subparsers.add_parser("benchmark")
    benchmark_sub = benchmark.add_subparsers(dest="benchmark_command", required=True)
    benchmark_run = benchmark_sub.add_parser("run")
    benchmark_run.add_argument("benchmark_name", choices=["line-follower"])
    benchmark_run.add_argument("--controller", default="example")
    benchmark_run.add_argument("--output", required=True)
    benchmark_run.add_argument("--duration-s", type=float, default=20.0)
    benchmark_report = benchmark_sub.add_parser("report")
    benchmark_report.add_argument("report_path")

    mcp_parser = subparsers.add_parser("mcp")
    mcp_sub = mcp_parser.add_subparsers(dest="mcp_command", required=True)
    mcp_sub.add_parser("serve")
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "doctor":
        print(format_doctor_report(run_doctor()))
        return

    if args.command == "session":
        if args.session_command == "start":
            manifest = start_session(
                world=args.world,
                controller=args.controller,
                mode=args.mode,
                render=args.render == "on",
            )
            print(json.dumps(manifest.to_dict(), indent=2))
            return
        if args.session_command == "stop":
            result = SessionClient.from_session(args.session).request("stop")
            print(json.dumps(result, indent=2))
            return

    if args.command == "benchmark":
        if args.benchmark_command == "run":
            report = run_line_follower_benchmark(
                controller=args.controller,
                output=Path(args.output),
                duration_s=args.duration_s,
            )
            print(json.dumps(report.to_dict(), indent=2))
            return
        if args.benchmark_command == "report":
            print(format_benchmark_report(Path(args.report_path)))
            return

    if args.command == "mcp" and args.mcp_command == "serve":
        run_mcp_server()


if __name__ == "__main__":
    main()
