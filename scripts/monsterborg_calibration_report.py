from __future__ import annotations

import argparse
import json
from pathlib import Path

from webots_mcp_kit.monsterborg_calibration import build_calibration_report


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare MonsterBorg Webots and physical export bundles.")
    parser.add_argument("--sim-export", required=True, type=Path)
    parser.add_argument("--physical-export", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    report = build_calibration_report(sim_export=args.sim_export, physical_export=args.physical_export)
    output = args.output if args.output.is_absolute() else (Path.cwd() / args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
