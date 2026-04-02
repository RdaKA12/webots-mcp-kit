from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

from webots_mcp_kit.gate import build_v1_gate_steps


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", required=True, help="Workspace used for generated gate artifacts.")
    parser.add_argument("--print-only", action="store_true", help="Print the planned commands without executing them.")
    return parser.parse_args(argv)


def run_cli(args: tuple[str, ...], *, timeout: int = 600) -> str:
    completed = subprocess.run(
        [sys.executable, "-m", "webots_mcp_kit.cli", *args],
        check=True,
        text=True,
        capture_output=True,
        timeout=timeout,
    )
    return completed.stdout


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    workspace = Path(args.workspace).resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    reports_dir = workspace / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    plans_dir = workspace / "plans"
    plans_dir.mkdir(parents=True, exist_ok=True)
    bundle_root = Path(__file__).resolve().parents[1] / "examples"
    imported_world_source = bundle_root / "line-follower" / "worlds" / "line_follower_benchmark.wbt"
    imported_world_copy = workspace / "editable-imported-line.wbt"
    imported_world_copy.write_text(imported_world_source.read_text(encoding="utf-8"), encoding="utf-8")
    (plans_dir / "generated-waypoint-world-edit.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "operations": [
                    {"type": "set_spawn", "translation": [-0.6, 0.0, 0.0], "rotation_z": 0.0},
                    {"type": "add_landmark", "name": "gate-landmark", "position": [0.1, 0.1], "radius": 0.04},
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (plans_dir / "imported-world-edit.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "operations": [
                    {"type": "add_landmark", "name": "imported-gate-landmark", "position": [0.0, 0.0], "radius": 0.04},
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    summary: list[dict[str, str]] = []
    session_ids: dict[str, str] = {}

    steps = build_v1_gate_steps(workspace)
    for step in steps:
        if step.name == "clean_user_acceptance":
            rendered = f"python scripts/clean_user_acceptance.py --workspace {workspace / 'acceptance'}"
            print(f"[v1-gate] {step.name}: {rendered}")
            if args.print_only:
                continue
            subprocess.run(
                [sys.executable, "scripts/clean_user_acceptance.py", "--workspace", str(workspace / "acceptance")],
                check=True,
                text=True,
                timeout=900,
            )
            summary.append({"step": step.name, "status": "ok"})
            continue

        raw_args = list(step.args)
        tokens = sorted({item for item in raw_args if re.fullmatch(r"\{[a-z0-9_]+\}", item)})
        for token in tokens:
            value = session_ids.get(token.strip("{}"))
            if value is None and args.print_only:
                value = f"<{token.strip('{}')}>"
            if value is None:
                raise RuntimeError(f"No session id available for step {step.name}.")
            raw_args = [value if item == token else item for item in raw_args]
        rendered = " ".join(raw_args)
        print(f"[v1-gate] {step.name}: webots-kit {rendered}")
        if args.print_only:
            continue
        stdout = run_cli(tuple(raw_args), timeout=1200 if "benchmark" in step.name else 600)
        if step.name.endswith("_session_start"):
            payload = json.loads(stdout)
            session_ids[f"{step.name.replace('_session_start', '')}_session_id"] = payload["session_id"]
        summary.append({"step": step.name, "status": "ok"})

    summary_path = workspace / "v1-gate-summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"[v1-gate] summary: {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
