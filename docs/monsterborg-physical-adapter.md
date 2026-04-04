# MonsterBorg Physical Adapter

Use this lane when you want Raspberry Pi MonsterBorg telemetry to land in the same export and replay format as the Webots runtime.

Supported scope:

- `monsterborg-4wd`
- Raspberry Pi host
- shared benchmark and replay artifacts
- export and replay parity

Not supported here:

- live MCP control of the physical robot
- generic Linux runtime support
- non-MonsterBorg hardware adapters

## Verify The Pi Environment

```powershell
python .\scripts\monsterborg_physical_verify.py --json
```

Green condition:

- `status: ready`
- `runtime_target: monsterborg-physical`
- ThunderBorg and bus dependencies are visible to Python

## Convert A Capture Into A Replay Bundle

Prepare a JSON file with either:

- a top-level sample array, or
- an object with `samples`, optional `benchmark_report`, and optional `physical_adapter_summary`

Then run:

```powershell
python .\scripts\monsterborg_capture_run.py --input .\capture.json --output .\artifacts\monsterborg-physical --scenario obstacle-avoidance --benchmark obstacle-avoidance --robot-name monsterborg-physical
webots-kit session replay .\artifacts\monsterborg-physical
```

Green condition:

- the capture script writes `export.json` and the standard artifact set
- `session replay` prints a readable observability summary for the physical run

## Output Contract

The physical adapter bundle preserves:

- `artifact_standard_version = 1`
- `runtime_target = monsterborg-physical`
- `robot_family = monsterborg`
- `robot_profile = monsterborg-4wd`

The replay path stays additive. Existing Webots exports remain unchanged.

Next:

- use [Project import and session replay](./project-import-and-replay.md) when you need the broader import and handoff flow
