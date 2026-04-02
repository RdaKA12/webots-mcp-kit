# Zero-to-Sim Guide

`webots-mcp-kit` now supports a template-driven path from an empty folder to a runnable Webots scenario.

Status:

- the CLI command names are treated as stable
- the generated JSON spec shape is `experimental-foundation`
- additive schema refinement is still allowed before the dedicated zero-to-sim deepening milestone

## Supported templates

- `epuck-arena`
- `epuck-line-track`
- `epuck-waypoint`
- `epuck-obstacle-course`

These templates are deterministic. The toolkit generates a JSON scenario spec first, then builds a world and controller scaffold from that spec.

## Quick start

```powershell
webots-kit project init .\my-webots-project
webots-kit scenario init .\my-webots-project\scenarios\warehouse-demo --template epuck-waypoint
webots-kit scenario validate .\my-webots-project\scenarios\warehouse-demo\webots-kit.scenario.json
webots-kit scenario build .\my-webots-project\scenarios\warehouse-demo\webots-kit.scenario.json
webots-kit scenario describe .\my-webots-project\scenarios\warehouse-demo\webots-kit.scenario.json
webots-kit scenario doctor .\my-webots-project\scenarios\warehouse-demo\webots-kit.scenario.json
```

## Generated files

The build step writes:

- `scenarios/<name>/webots-kit.scenario.json`
- `scenarios/<name>/worlds/<name>.wbt`
- `scenarios/<name>/controllers/<name>_agent.py`
- `scenarios/<name>/benchmark.config.json`
- `scenarios/<name>/webots-kit.generated.json`

## Scenario spec shape

The generated spec is JSON-first and agent-friendly:

- `project`
- `scenario`
- `robot`
- `environment`
- `layout`
- `task`
- `controller`
- `benchmark`
- `sensors`
- `actuators`

The toolkit validates the spec before build. Unsupported template/task combinations fail fast with structured error codes.

## Runtime flow after build

The generated metadata includes suggested commands. The typical next steps are:

```powershell
webots-kit session start --scenario waypoint-nav --world .\scenarios\warehouse-demo\worlds\warehouse-demo.wbt --controller .\scenarios\warehouse-demo\controllers\warehouse-demo_agent.py --robot-name epuck-warehouse-demo-waypoint-nav --robot-def EPUCK --mode fast --render off
webots-kit benchmark run waypoint-nav --controller .\scenarios\warehouse-demo\controllers\warehouse-demo_agent.py --world .\scenarios\warehouse-demo\worlds\warehouse-demo.wbt --robot-name epuck-warehouse-demo-waypoint-nav --robot-def EPUCK --output .\scenarios\warehouse-demo\artifacts\report.json
```

## Current limits

- This is template-driven, not free-form natural language to `.wbt`.
- The first robot family is `e-puck`.
- Arena generation is currently rectangle-based.
- Runtime smoke still requires an interactive self-hosted runner labeled `interactive-webots`.
