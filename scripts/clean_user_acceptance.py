from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from webots_mcp_kit.acceptance import (
    FULL_ACCEPTANCE_PROFILE,
    HOSTED_SAFE_ACCEPTANCE_PROFILE,
    build_clean_user_acceptance_steps,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", required=True, help="Workspace root used for clean-user acceptance output.")
    parser.add_argument(
        "--profile",
        default=FULL_ACCEPTANCE_PROFILE,
        choices=[FULL_ACCEPTANCE_PROFILE, HOSTED_SAFE_ACCEPTANCE_PROFILE],
        help="Acceptance profile. Use hosted-safe on runners without Webots.",
    )
    parser.add_argument("--print-only", action="store_true", help="Print the planned commands without executing them.")
    return parser.parse_args(argv)


def enrich_waypoint_spec(spec_path: Path) -> None:
    payload = json.loads(spec_path.read_text(encoding="utf-8"))
    layout = payload.setdefault("layout", {})
    layout["walls"] = [
        {"name": "wall-north-divider", "start": [-0.2, -0.3], "end": [-0.2, 0.3], "thickness": 0.02, "height": 0.08}
    ]
    layout["landmarks"] = [
        {"name": "landmark-pickup-marker", "position": [0.2, -0.2], "radius": 0.04}
    ]
    layout["zones"] = [
        {"name": "zone-goal-buffer", "center": [0.45, 0.0], "size": [0.22, 0.22]}
    ]
    layout["props"] = [
        {"name": "prop-crate-a", "position": [0.0, 0.45], "size": [0.08, 0.08, 0.08]}
    ]
    spec_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    workspace = Path(args.workspace)
    workspace.mkdir(parents=True, exist_ok=True)
    steps = build_clean_user_acceptance_steps(workspace, profile=args.profile)

    for step in steps:
        rendered = " ".join(step.args)
        if step.name == "scenario_enrich":
            print(f"[acceptance] {step.name}: enrich scenario spec {rendered}")
            if args.print_only:
                continue
            enrich_waypoint_spec(Path(step.args[0]))
            continue
        if step.name == "mcp_authoring_smoke":
            rendered = f"python scripts/mcp_authoring_smoke.py --workspace {step.args[0]}"
            print(f"[acceptance] {step.name}: {rendered}")
            if args.print_only:
                continue
            subprocess.run(
                [sys.executable, "scripts/mcp_authoring_smoke.py", "--workspace", step.args[0]],
                check=True,
                text=True,
            )
            continue
        if step.name == "upgrade_check":
            rendered = f"powershell -ExecutionPolicy Bypass -File scripts\\upgrade_check.ps1 -Workspace {step.args[0]} -Runtime"
            print(f"[acceptance] {step.name}: {rendered}")
            if args.print_only:
                continue
            subprocess.run(
                [
                    "powershell",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    "scripts\\upgrade_check.ps1",
                    "-Workspace",
                    step.args[0],
                    "-Runtime",
                ],
                check=True,
                text=True,
            )
            continue

        print(f"[acceptance] {step.name}: webots-kit {rendered}")
        if args.print_only:
            continue
        subprocess.run(
            [sys.executable, "-m", "webots_mcp_kit.cli", *step.args],
            check=True,
            text=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
