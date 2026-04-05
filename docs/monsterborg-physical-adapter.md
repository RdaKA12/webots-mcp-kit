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

## Compare Sim And Physical Runs

When you want a parity report between a Webots export and a physical MonsterBorg export, run:

```powershell
python .\scripts\monsterborg_calibration_report.py --sim-export .\artifacts\monsterborg-sim --physical-export .\artifacts\monsterborg-physical --output .\artifacts\monsterborg-calibration.json
```

The calibration report compares:

- `mean_forward_speed`
- `encoder_distance`
- `heading_drift`
- `line_reacquisition_events`
- `max_line_reacquisition_steps`
- `collision_count`

Green condition:

- `pass: true`
- `next_step` is either a no-op summary or a small tuning action

Next:

- use [Project import and session replay](./project-import-and-replay.md) when you need the broader import and handoff flow
