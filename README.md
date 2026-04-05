# webots-mcp-kit

`webots-mcp-kit` is a Windows-first toolkit for running Webots with a stable CLI, MCP server, controller SDK, bundled benchmarks, and structured world/controller authoring workflows. `v2.8.0` hardens MonsterBorg line-follow with richer track variants, stronger controller telemetry, and a sim-to-real calibration report on top of the existing `e-puck` and MonsterBorg runtime surfaces.

## Support Matrix

| Area | Supported |
| --- | --- |
| OS | Windows |
| Webots | `R2025a` |
| Python | `3.11+` |
| Runtime model | `interactive-webots` |
| Robot family | `e-puck`, `MonsterBorg 4WD` |
| Package distribution | PyPI + GitHub |
| Runtime workflows | `doctor`, `session`, `benchmark`, `import/export/replay` |
| Authoring workflows | `controller scaffold/inspect/edit/validate`, `world inspect/validate/edit`, `scenario init/validate/build/doctor` |

Supported baseline: Windows, Webots `R2025a`, Python `3.11+`, `interactive-webots`, `e-puck`, plus `MonsterBorg 4WD` Webots support and the Raspberry Pi physical-adapter lane on the current release line.

## Unsupported Matrix

| Area | Not supported on `v2.8.0` |
| --- | --- |
| Runtime | Windows service runner, Linux, macOS, live MCP control of physical robots |
| Robotics stack | ROS2, multi-robot orchestration |
| World generation | free-form natural-language-to-world generation |
| Distribution | `.exe`, `winget`, standalone website, marketplace/app-directory packaging |
| Physical robot lane | general Linux runtime, non-MonsterBorg hardware adapters |

## 5-Minute Quickstart

From a repo checkout on a Windows machine with Webots `R2025a` installed:

```powershell
pipx install webots-mcp-kit
powershell -ExecutionPolicy Bypass -File .\scripts\verify_install.ps1 -Runtime
```

That path verifies:

- `doctor`
- bundled benchmark discovery
- temporary controller scaffold + validate
- bundled world inspect
- a short real `line-follower` benchmark

MonsterBorg verification uses the same public script:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\verify_install.ps1 -RobotProfile monsterborg-4wd -Runtime
```

If `pipx` is not installed yet, use the helper:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\verify_install.ps1 -Runtime
```

## Choose Your Path

- Connect an agent: start with [First hour guide](./docs/first-hour-guide.md)
- Write or edit a controller: start with [Controller authoring and editing](./docs/controller-authoring-and-editing.md)
- Inspect or edit a world: start with [World authoring and editing](./docs/world-authoring-and-editing.md)
- Import an existing project and replay a session: start with [Project import and session replay](./docs/project-import-and-replay.md)

## For Teams

Use the team starter workspaces when you want a repeatable path that can be handed to another developer without extra setup decisions:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\bootstrap_workspace.ps1 -Starter line-follower -Destination .\workspaces\line-follower-demo
powershell -ExecutionPolicy Bypass -File .\scripts\upgrade_check.ps1 -Workspace .\artifacts\upgrade-check -Runtime
```

MonsterBorg starter workspaces:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\bootstrap_workspace.ps1 -Starter monsterborg-line-follower -Destination .\workspaces\monsterborg-line-follower
powershell -ExecutionPolicy Bypass -File .\scripts\upgrade_check.ps1 -Workspace .\artifacts\monsterborg-upgrade-check -RobotProfile monsterborg-4wd -Runtime
```

Use [Team flows](./docs/team-flows.md) when you want the exact command sequence for:

- evaluator flow
- controller author flow
- world author flow
- importer and triage flow

## Install And Upgrade

Primary install path:

```powershell
pipx install webots-mcp-kit
```

Upgrade with the same tool:

```powershell
pipx upgrade webots-mcp-kit
```

Repo-assisted install from a checkout:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1
```

Fallback path when you do not want `pipx`:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install webots-mcp-kit
```

Packaging, pinned-version, and wheel-install details live in [PyPI install and upgrade](./docs/pypi-install-and-upgrade.md).
Upgrade and post-release verification live in [Upgrade guide](./docs/upgrade-guide.md).

## Troubleshooting

If install or runtime verification fails, start with [Troubleshooting](./docs/troubleshooting.md).

## Bundled Scenarios

- `line-follower`: camera-based line tracking and the canonical first-success benchmark
- `obstacle-avoidance`: proximity-sensor or front-range obstacle avoidance
- `waypoint-nav`: waypoint navigation with benchmarked goal progress

Robot profiles:

- `e-puck`: stable bundled task-world baseline
- `monsterborg-4wd`: bundled support with generated templates, bundled Webots examples, and robot-aware controller/world/import flows

## CLI And MCP Overview

Core CLI areas:

- runtime: `doctor`, `session start/inspect/logs/export/replay/stop`, `benchmark list/run/report`
- controller authoring: `controller scaffold`, `controller inspect`, `controller edit`, `controller validate`
- world authoring: `world inspect`, `world validate`, `world edit`
- zero-to-sim: `project init`, `scenario init`, `scenario validate`, `scenario build`, `scenario describe`, `scenario doctor`
- import/replay: `project import`, `session export`, `session replay`
- MCP bridge: `mcp serve`

Additive robot-aware flags:

- `--robot-profile e-puck`
- `--robot-profile monsterborg-4wd`

Core MCP tools:

- runtime: `webots_session_start`, `webots_get_state`, `webots_get_sensors`, `webots_capture_camera`, `webots_run_benchmark`
- world authoring: `webots_world_inspect`, `webots_world_validate`, `webots_world_edit`
- controller authoring: `webots_controller_scaffold`, `webots_controller_inspect`, `webots_controller_validate`, `webots_controller_edit`

Authoring workflows are supported on the stable release line, but the deeper schema surfaces remain `experimental-foundation` and additive. In `v2.8.0`, the MonsterBorg line-follow hardening, variant bundle, and calibration report lane ship on the stable release line while keeping their additive schema posture.

MonsterBorg line-follow preview extras:

- bundled variant specs under `examples/monsterborg/line-follower/variants`
- richer `benchmark report` and `session replay` line-follow metrics
- `python scripts/monsterborg_calibration_report.py --sim-export <dir> --physical-export <dir> --output <json>`

## Docs Map

- [First hour guide](./docs/first-hour-guide.md)
- [Onboarding flows](./docs/onboarding-flows.md)
- [Team flows](./docs/team-flows.md)
- [Troubleshooting](./docs/troubleshooting.md)
- [PyPI install and upgrade](./docs/pypi-install-and-upgrade.md)
- [Upgrade guide](./docs/upgrade-guide.md)
- [Version policy](./docs/version-policy.md)
- [MonsterBorg physical adapter](./docs/monsterborg-physical-adapter.md)
- [Controller authoring and editing](./docs/controller-authoring-and-editing.md)
- [World authoring and editing](./docs/world-authoring-and-editing.md)
- [Custom controller integration](./docs/custom-controller-integration.md)
- [Zero-to-sim guide](./docs/zero-to-sim.md)
- [Project import and session replay](./docs/project-import-and-replay.md)
- [MCP contracts](./docs/mcp-contracts.md)
- [Self-hosted runtime smoke](./docs/self-hosted-windows-runner.md)
- [Release checklist](./docs/release-checklist.md)
