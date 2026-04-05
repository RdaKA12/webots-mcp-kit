# Project Import and Session Replay

`webots-mcp-kit` can now bring existing Webots assets into a kit-managed workflow and export finished sessions for later triage.

Status:

- `project import`, `session export`, and `session replay` are supported foundation workflows in `v1.2.0`
- the CLI command names are stable
- replay/export metadata and deeper file schemas remain `experimental-foundation` and additive

## Import an existing project

```powershell
webots-kit project import --world .\worlds\demo.wbt --controller .\controllers\demo_agent.py
```

The import command:

- discovers or creates a project root
- writes `webots-kit.project.json` if needed
- creates `scenarios/imported-<world-name>/webots-kit.scenario.json`
- records the original world/controller paths in `import_source`
- discovers `discovered_robot_name`, `discovered_robot_def`, and `discovered_devices`
- discovers `discovered_robot_family`, `suggested_robot_profile`, and `runtime_target`
- reports whether the imported lane can participate in the future `physical_adapter_supported` workflow
- suggests a benchmark profile through `suggested_benchmark_name`
- returns `minimal_scenario_metadata` so the imported scenario can be validated or evolved deterministically

This does not rewrite the imported world. It creates kit metadata so the project can be inspected and evolved with later zero-to-sim commands.

## Export a session

```powershell
webots-kit session export 123456abcdef --output .\artifacts\exports\123456abcdef
```

The export bundle includes:

- `doctor.json`
- `session.json`
- `inspect.json`
- `log_inventory.json`
- `log_summary.json`
- `runtime_environment.json`
- `summary.json`
- `export.json`
- copied log files under `logs/`
- copied session artifacts under `artifacts/`

`export.json` is the canonical manifest for the export bundle. It pins:

- the standard artifact version
- the replay mode
- the paths of the standard JSON artifacts
- copied log and artifact locations
- additive scenario/result metadata such as `scenario`, `status`, `last_error_code`, and `result_reason`
- additive robot/runtime metadata such as `robot_family`, `robot_profile`, `runtime_target`, and `physical_adapter_summary`

## Replay an exported session

```powershell
webots-kit session replay .\artifacts\exports\123456abcdef
```

`session replay` also accepts the canonical `export.json` path directly when you want to point at an already-exported manifest.

Replay is observability-focused. It does not rerun physics. Instead, it gives you:

- the last known session state
- the replay mode and artifact standard version
- the last structured runtime error
- the runtime summary and runtime environment used for that session
- a `benchmark_summary` for the last known benchmark-facing outcome
- a `telemetry_summary` derived from the exported runtime summary
- a `runtime_failure_class` plus `triage_recipe`
- additive authoring/runtime metadata including `robot_family`, `robot_profile`, and `runtime_target`
- additive benchmark-facing metadata such as `task_variant` and `task_quality_summary` when the exported run came from the hardened MonsterBorg task lanes
- the copied log summary captured at export time
- copied logs and artifacts
- the suggested next step for triage or rerun

Next: continue with [World authoring and editing](./world-authoring-and-editing.md) if the replay outcome tells you the imported world needs a structured patch, or use [Team flows](./team-flows.md) for the importer/triage lane.
