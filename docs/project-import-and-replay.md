# Project Import and Session Replay

`webots-mcp-kit` can now bring existing Webots assets into a kit-managed workflow and export finished sessions for later triage.

Status:

- `project import`, `session export`, and `session replay` command names are treated as stable
- their file formats and metadata are `experimental-foundation` until the post-`v1.0.0` replay/import expansion milestone

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
- copied log files under `logs/`
- copied session artifacts under `artifacts/`

## Replay an exported session

```powershell
webots-kit session replay .\artifacts\exports\123456abcdef
```

Replay is observability-focused. It does not rerun physics. Instead, it gives you:

- the last known session state
- the last structured runtime error
- copied logs and artifacts
- the runtime environment used for that session
- the suggested next step for triage or rerun
