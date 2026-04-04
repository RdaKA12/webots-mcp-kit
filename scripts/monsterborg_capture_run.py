from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from webots_mcp_kit.monsterborg_adapter import build_monsterborg_physical_bundle


def _load_capture(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return {"samples": payload}
    if not isinstance(payload, dict):
        raise ValueError("Capture input must be a JSON object or a JSON array.")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Convert a MonsterBorg physical capture JSON file into an export/replay bundle.")
    parser.add_argument("--input", required=True, help="Path to a JSON file containing `samples` or a top-level sample array.")
    parser.add_argument("--output", required=True, help="Export directory to create.")
    parser.add_argument("--scenario", default="waypoint-nav", help="Scenario name recorded by the capture.")
    parser.add_argument("--benchmark", default=None, help="Benchmark name associated with the capture.")
    parser.add_argument("--robot-name", default="monsterborg-physical", help="Logical robot name to write into the export bundle.")
    args = parser.parse_args()

    payload = _load_capture(Path(args.input))
    samples = payload.get("samples", [])
    if not isinstance(samples, list) or not samples:
        raise ValueError("Capture input must contain a non-empty `samples` array.")

    result = build_monsterborg_physical_bundle(
        output_dir=Path(args.output),
        scenario=args.scenario,
        robot_name=args.robot_name,
        samples=samples,
        benchmark_name=args.benchmark or args.scenario,
        benchmark_report=payload.get("benchmark_report") if isinstance(payload.get("benchmark_report"), dict) else None,
        physical_adapter_summary=payload.get("physical_adapter_summary")
        if isinstance(payload.get("physical_adapter_summary"), dict)
        else None,
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
