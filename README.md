# webots-mcp-kit

`webots-mcp-kit` is a Windows-first developer toolkit for connecting LLM agents to Webots.

It combines:

- a pip-installable CLI
- an MCP server with Webots session tools
- a controller-side SDK for structured telemetry and manual overrides
- bundled example scenarios and benchmarks

The bundled line follower is not the product itself. It is the first reference example.
The toolkit is meant to be reusable across other Webots robots, controllers, and worlds.

## Release

`v1.6.0`

Stable baseline:

- Windows-first local development
- Webots `R2025a`
- direct Webots integration without ROS2
- stable controller-side integration through `ControllerAgent`
- bundled scenarios plus registry-backed benchmark thresholds
- hosted-safe CI with separate self-hosted runtime smoke
- release pipeline for GitHub Release, TestPyPI, and PyPI
- public-contract regression coverage and external-user onboarding
- MCP reliability for LLM-driven Webots sessions
- zero-to-sim foundations through template-driven project and scenario generation
- standardized runtime artifact and replay bundles for exported sessions
- centralized clean-user acceptance flow for package and publish smoke
- explicit no-mock `v1.0.0` gate validation for real runtime workflows
- richer zero-to-sim validation, doctoring, and generated runtime smoke across all three bundled task families
- deterministic import discovery and replay triage summaries for existing project workflows
- experimental agent-authoring foundations for controller inspect/edit and world inspect/validate/edit
- generated and imported world authoring runtime smoke on the structured authoring surface
- richer from-scratch world authoring for `walls`, `landmarks`, `zones`, and `props` across generated scenarios
- MCP authoring parity smoke and split onboarding flows for world/controller authoring

Operational runtime model:

- `interactive-webots` is the single supported runtime execution path for real Webots sessions, benchmarks, and runtime smoke
- Windows service mode is not a supported runtime path

## Support statement

Supported:

- Windows
- Webots `R2025a`
- Python `3.11+`
- interactive self-hosted runtime through the `interactive-webots` runner label as the only supported runtime execution model
- foundation workflows for `project init`, `scenario init`, `scenario validate`, `scenario build`, `scenario describe`, `scenario doctor`, `project import`, `session export`, and `session replay`
- experimental-foundation authoring workflows for `controller scaffold`, `controller inspect`, `controller edit`, `controller validate`, `world inspect`, `world validate`, `world edit`, and the matching `webots_controller_*` / `webots_world_*` MCP tools

Foundation schema note:

- CLI command names are stable in `v1.2.0`
- the documented core `ScenarioSpec` subset is stable in `v1.1.0`
- the wider JSON schema remains additive and `experimental-foundation`

Unsupported at `v1.0.0`:

- Windows service runner runtime
- Linux/macOS runtime support
- ROS2 integration
- multi-robot orchestration
- free-form natural-language-to-world generation

## Bundled scenarios

- `line-follower`
  - camera-based line tracking
  - example world: `examples/line-follower`
- `obstacle-avoidance`
  - proximity-sensor obstacle avoidance
  - example world: `examples/obstacle-avoidance`
- `waypoint-nav`
  - fixed-waypoint navigation in an open arena
  - example world: `examples/waypoint-nav`

## Install

Use an isolated virtual environment. The toolkit depends on `mcp`, which may pull shared web stack packages into your global Python install.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install webots-mcp-kit
```

Development install:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e .[dev]
```

Optional CI or slow-machine tuning:

```powershell
$env:WEBOTS_KIT_SESSION_START_TIMEOUT='90'
```

## Quick start

### I want to connect an agent to Webots

```powershell
webots-kit doctor
webots-kit session start --scenario line-follower --controller example --mode fast --render off
webots-kit mcp serve
webots-kit benchmark list
webots-kit benchmark run line-follower --controller example --output .\report.json --duration-s 3
webots-kit benchmark report .\report.json
```

### I want to integrate my own controller

```powershell
webots-kit controller scaffold .\controllers\my_agent.py --scenario line-follower
webots-kit controller inspect .\controllers\my_agent.py --scenario line-follower
webots-kit controller validate .\controllers\my_agent.py --scenario line-follower --strict --json
webots-kit benchmark run line-follower --controller .\controllers\my_agent.py --output .\report.json
```

### I want to inspect or edit a world

```powershell
webots-kit world inspect .\worlds\demo.wbt
webots-kit world validate .\worlds\demo.wbt
webots-kit world edit .\worlds\demo.wbt --plan .\plans\world-edit.json
```

### I want to generate a scenario from a spec

```powershell
webots-kit project init .\my-webots-project
webots-kit scenario init .\my-webots-project\scenarios\warehouse-demo --template epuck-waypoint
webots-kit scenario validate .\my-webots-project\scenarios\warehouse-demo\webots-kit.scenario.json
webots-kit scenario build .\my-webots-project\scenarios\warehouse-demo\webots-kit.scenario.json
webots-kit scenario doctor .\my-webots-project\scenarios\warehouse-demo\webots-kit.scenario.json
```

### I want to import and replay

```powershell
webots-kit project import --world .\worlds\demo.wbt --controller .\controllers\demo_agent.py
webots-kit session export <session-id> --output .\artifacts\exports\<session-id>
webots-kit session replay .\artifacts\exports\<session-id>
```

## CLI surface

- `webots-kit doctor [--json]`
- `webots-kit session start --scenario <name> --world <path> --controller <path-or-id> [--robot-name <name>] [--robot-def <def>] [--mode fast|realtime|pause] [--render on|off]`
- `webots-kit session inspect --session <id>`
- `webots-kit session logs --session <id> [--name <file>] [--tail <n>]`
- `webots-kit session export <id> [--output <path>]`
- `webots-kit session replay <export-path> [--json]`
- `webots-kit session stop --session <id>`
- `webots-kit benchmark list`
- `webots-kit benchmark run <scenario> --controller <path-or-id> --output <report.json> [--duration-s <seconds>] [--world <path>] [--robot-name <name>] [--robot-def <def>]`
- `webots-kit benchmark report <report.json>`
- `webots-kit controller validate <path> [--scenario <name>] [--strict] [--json]`
- `webots-kit controller scaffold <path> [--scenario <name>] [--language python|cpp] [--spec <spec.json>] [--world <path>] [--robot-name <name>] [--robot-def <def>] [--force]`
- `webots-kit controller inspect <path> [--scenario <name>] [--json]`
- `webots-kit controller edit <path> --plan <controller-edit.json>`
- `webots-kit project init <path> [--name <name>] [--force]`
- `webots-kit project import --world <path> --controller <path> [--project-root <path>]`
- `webots-kit scenario init <path> --template <template> [--force]`
- `webots-kit scenario validate <spec-path> [--json]`
- `webots-kit scenario build <spec-path> [--force]`
- `webots-kit scenario describe <spec-path>`
- `webots-kit scenario doctor <spec-path> [--json]`
- `webots-kit world inspect <wbt-path> [--json]`
- `webots-kit world validate <wbt-path> [--json]`
- `webots-kit world edit <wbt-path> --plan <world-edit.json>`
- `webots-kit mcp serve`

Supported zero-to-sim templates:

- `epuck-arena`
- `epuck-line-track`
- `epuck-waypoint`
- `epuck-obstacle-course`

Foundation status for the zero-to-sim surface:

- CLI command names are stable in `v1.0.0`
- the underlying JSON `ScenarioSpec` schema is still `experimental-foundation`
- the schema is documented, supported, and still additive until `v1.1.0`

## Controller integration

There are two supported usage paths:

- bundled example controllers under `examples/`
- user-supplied Python or C++ controllers that integrate with `ControllerAgent`

The public controller-side entrypoint is `ControllerAgent`.
The stable public contract is:

- `ControllerAgent.from_robot(...)`
- `begin_step()`
- `report_step(...)`

Minimal integration shape:

```python
from controller import Robot
from webots_mcp_kit.agent import ControllerAgent

robot = Robot()
agent = ControllerAgent.from_robot(robot, default_camera="camera")

while robot.step(int(robot.getBasicTimeStep())) != -1:
    override = agent.begin_step()
    # apply your control logic, optionally overriding wheel commands
    agent.report_step(
        sensors={},
        metrics={},
        actuators={},
        camera_frames=None,
    )
```

Use `webots-kit controller validate <path>` to check whether a controller follows the expected integration pattern.
Use `webots-kit controller scaffold` when you want a working starter file based on a bundled scenario.
Use `webots-kit controller inspect` and `webots-kit controller edit` when an agent needs structured visibility and safe patch regions.

## MCP tools

- `webots_session_start`
- `webots_session_stop`
- `webots_list_robots`
- `webots_list_devices`
- `webots_get_state`
- `webots_get_sensors`
- `webots_capture_camera`
- `webots_set_motor_velocity`
- `webots_step`
- `webots_pause_resume`
- `webots_reset`
- `webots_run_benchmark`
- `webots_world_inspect`
- `webots_world_validate`
- `webots_world_edit`
- `webots_controller_inspect`
- `webots_controller_scaffold`
- `webots_controller_validate`
- `webots_controller_edit`

Stable payload shapes:

- `webots_session_start ->` stable session/readiness top-level keys with additive extras only
- `webots_get_state -> { session, session_state, control_paused, runtime_summary, runtimes }`
- `webots_list_devices -> { robot, scenario, devices }`
- `webots_get_sensors -> { robot, scenario, state, sensors, metrics, actuators, meta }`
- `webots_capture_camera -> { path, width, height }`
- `webots_run_benchmark ->` stable benchmark report top-level keys with additive `extra_metrics`
- `webots_world_*` and `webots_controller_*` use explicit normalized top-level payloads documented in [MCP contracts](./docs/mcp-contracts.md)
- failed MCP tool calls -> `{ ok: false, error: { code, message, details, retriable } }`
- existing MCP/runtime failure codes are stable at `v1.0.0`; new codes may only be added

Reference docs:

- [Onboarding flows](./docs/onboarding-flows.md)
- [Controller authoring and editing](./docs/controller-authoring-and-editing.md)
- [World authoring and editing](./docs/world-authoring-and-editing.md)
- [v1.0.0 gate](./docs/v1-gate.md)
- [First hour guide](./docs/first-hour-guide.md)
- [MCP contracts](./docs/mcp-contracts.md)
- [Self-hosted runtime smoke](./docs/self-hosted-windows-runner.md)
- [Custom controller integration](./docs/custom-controller-integration.md)
- [Controller authoring and editing](./docs/controller-authoring-and-editing.md)
- [Add a new scenario](./docs/new-scenario-guide.md)
- [Zero-to-sim guide](./docs/zero-to-sim.md)
- [World authoring and editing](./docs/world-authoring-and-editing.md)
- [Project import and session replay](./docs/project-import-and-replay.md)
- [Failed runtime smoke triage](./docs/failed-runtime-smoke-triage.md)
- [PyPI install and upgrade](./docs/pypi-install-and-upgrade.md)
- [Release checklist](./docs/release-checklist.md)
- [Runner maintenance](./docs/self-hosted-runner-maintenance.md)
- [Packaging verification](./docs/packaging-verification-checklist.md)

## Testing

Unit tests:

```powershell
python -m pytest -q
```

Hosted-safe smoke tests:

```powershell
$env:WEBOTS_KIT_RUN_SMOKE='1'
python -m pytest -q -k mcp_tool_list_smoke
```

Full runtime smoke tests with real Webots execution:

```powershell
$env:WEBOTS_KIT_RUN_RUNTIME_SMOKE='1'
python -m pytest -q -k "session_start_inspect_stop_smoke or benchmark_smoke or generated_scenario_smoke or generated_world_edit_smoke or imported_project_smoke or imported_world_edit_smoke or mcp_contract_smoke or mcp_authoring_contract_smoke or session_export_replay_diagnostics_smoke"
```

The self-hosted GitHub workflow for runtime smoke expects a Windows runner labeled `interactive-webots`.
That runner must be started from an interactive user session. Windows service mode is not sufficient for Webots runtime smoke because Webots exits during OpenGL initialization before controllers connect.
The self-hosted runtime workflow also auto-triggers for runtime-affecting changes and still supports manual dispatch.
Packaging and release verification are handled by GitHub workflows:

- `Packaging CI`
- `Release`

## Troubleshooting

- If `doctor` fails, ensure `WEBOTS_HOME` is set or Webots is installed in `C:\Program Files\Webots`.
- If MCP or session startup closes immediately, inspect `session logs` for the session artifacts.
- Session failures now report structured error codes such as `render-init-failed`, `agent-connect-timeout`, and `supervisor-connect-timeout`.
- If package installation changes global Python web dependencies, recreate a dedicated virtual environment and reinstall there.
- GitHub-hosted `windows-latest` runners are only used for unit tests, `doctor`, and MCP handshake smoke. Real Webots runtime smoke is exposed as a separate manual workflow for self-hosted Windows runners with Webots installed.
- Runtime-affecting changes now also path-trigger the self-hosted runtime workflow when the `interactive-webots` runner is available.
- `examples/` contains runnable demo assets; benchmark thresholds and pass/fail logic live in the benchmark registry inside the toolkit code.
- Wheel installs use bundled package-local scenario assets; source checkouts continue to use repo-local `examples/`.
- The self-hosted machine standard for runtime smoke is the runner-owned Python install at `D:\actions-runner\python311-shared`.
