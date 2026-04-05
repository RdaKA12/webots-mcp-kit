from __future__ import annotations

import argparse
import json
from pathlib import Path

from webots_mcp_kit.monsterborg_matrix import build_benchmark_matrix


def main() -> int:
    parser = argparse.ArgumentParser(description="Aggregate MonsterBorg benchmark reports or export directories into a tuning matrix.")
    parser.add_argument("paths", nargs="+", help="Benchmark report JSON files or export directories.")
    parser.add_argument("--output", required=True, help="Where to write the aggregated matrix JSON.")
    args = parser.parse_args()

    payload = build_benchmark_matrix([Path(item) for item in args.paths])
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
