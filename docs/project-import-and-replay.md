# Project Import and Session Replay

`webots-mcp-kit` can now bring existing Webots assets into a kit-managed workflow and export finished sessions for later triage.

Status:

- `project import`, `session export`, and `session replay` command names are treated as stable
- only the CLI command names are in the `v1.0.0` stable contract scope
- replay/export metadata and deeper file schemas remain `experimental-foundation` until the post-`v1.0.0` replay/import expansion milestone

## Import an existing project

```powershell
webots-kit project import --world .\worlds\demo.wbt --controller .\controllers\demo_agent.py
```

The import command:

- discovers or creates a project root
- writes `webots-kit.project.json` if needed
- creates `scenarios/imported-<world-name>/webots-kit.scenario.json`
- records the original world/controller paths in `import_source`

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
- the copied log summary captured at export time
- copied logs and artifacts
- the suggested next step for triage or rerun
