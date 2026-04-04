from __future__ import annotations

import argparse
import json

from webots_mcp_kit.monsterborg_adapter import verify_monsterborg_physical_environment


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify the MonsterBorg physical adapter prerequisites on a Raspberry Pi.")
    parser.add_argument("--json", action="store_true", help="Emit JSON only.")
    parser.add_argument("--camera-optional", action="store_true", help="Do not require Picamera2 for readiness.")
    args = parser.parse_args()

    payload = verify_monsterborg_physical_environment(camera_required=not args.camera_optional)
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(f"status: {payload['status']}")
        print(f"summary: {payload['summary']}")
        print(f"runtime_target: {payload['runtime_target']}")
        print(f"robot_profile: {payload['robot_profile']}")
        print(f"module_status: {payload['module_status']}")
        print(f"pi_model: {payload['platform'].get('pi_model')}")
        print(f"next_step: {payload['next_step']}")
    return 0 if payload["status"] == "ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
