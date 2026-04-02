from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from webots_mcp_kit.acceptance import build_clean_user_acceptance_steps


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", required=True, help="Workspace root used for clean-user acceptance output.")
    parser.add_argument("--print-only", action="store_true", help="Print the planned commands without executing them.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    workspace = Path(args.workspace)
    workspace.mkdir(parents=True, exist_ok=True)
    steps = build_clean_user_acceptance_steps(workspace)

    for step in steps:
        rendered = " ".join(step.args)
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
