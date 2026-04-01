# webots-mcp-kit

`webots-mcp-kit` is a Windows-first developer toolkit for connecting LLM agents to Webots.

It combines:

- a pip-installable CLI
- an MCP server with Webots session tools
- a controller-side SDK for structured telemetry and manual overrides
- bundled example scenarios and benchmarks

The bundled line follower is not the product itself. It is the first reference example.
The toolkit is meant to be reusable across other Webots robots, controllers, and worlds.

## Current release

`v0.9.0`

Current focus:

- Windows-first local development
- Webots `R2025a`
- direct Webots integration without ROS2
- stable controller-side integration through `ControllerAgent`
- bundled scenarios plus registry-backed benchmark thresholds
- hosted-safe CI with separate self-hosted runtime smoke
- release pipeline for GitHub Release, TestPyPI, and PyPI
- public-contract regression coverage and external-user onboarding

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

```powershell
webots-kit doctor
webots-kit benchmark list
webots-kit benchmark run line-follower --controller example --output .\report.json --duration-s 3
webots-kit benchmark report .\report.json
```

For an interactive session:

```powershell
webots-kit session start --scenario line-follower --controller example --mode fast --render off
webots-kit session inspect --session <session-id>
webots-kit session logs --session <session-id>
webots-kit session stop --session <session-id>
```

For a custom controller scaffold:

```powershell
webots-kit controller scaffold .\controllers\my_agent.py --scenario line-follower
webots-kit controller validate .\controllers\my_agent.py --scenario line-follower --strict --json
```

To expose the toolkit as an MCP server:

```powershell
webots-kit mcp serve
```

## CLI surface

- `webots-kit doctor [--json]`
- `webots-kit session start --scenario <name> --world <path> --controller <path-or-id> [--robot-name <name>] [--robot-def <def>] [--mode fast|realtime|pause] [--render on|off]`
- `webots-kit session inspect --session <id>`
- `webots-kit session logs --session <id> [--name <file>] [--tail <n>]`
- `webots-kit session stop --session <id>`
- `webots-kit benchmark list`
- `webots-kit benchmark run <scenario> --controller <path-or-id> --output <report.json> [--duration-s <seconds>]`
- `webots-kit benchmark report <report.json>`
- `webots-kit controller validate <path> [--scenario <name>] [--strict] [--json]`
- `webots-kit controller scaffold <path> [--scenario <name>] [--force]`
- `webots-kit mcp serve`

## Controller integration

There are two supported usage paths:

- bundled example controllers under `examples/`
- user-supplied Python controllers that integrate with `ControllerAgent`

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

Stable payload shapes:

- `webots_list_devices -> { robot, scenario, devices }`
- `webots_get_sensors -> { robot, scenario, state, sensors, metrics, actuators, meta }`

Reference docs:

- [First hour guide](./docs/first-hour-guide.md)
- [MCP contracts](./docs/mcp-contracts.md)
- [Self-hosted runtime smoke](./docs/self-hosted-windows-runner.md)
- [Custom controller integration](./docs/custom-controller-integration.md)
- [Add a new scenario](./docs/new-scenario-guide.md)
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
python -m pytest -q -k "session_start_inspect_stop_smoke or benchmark_smoke"
```

The self-hosted GitHub workflow for runtime smoke expects a Windows runner labeled `webots`.
The self-hosted runtime workflow also auto-triggers for runtime-affecting changes and still supports manual dispatch.
Packaging and release verification are handled by GitHub workflows:

- `Packaging CI`
- `Release`

## Troubleshooting

- If `doctor` fails, ensure `WEBOTS_HOME` is set or Webots is installed in `C:\Program Files\Webots`.
- If MCP or session startup closes immediately, inspect `session logs` for the session artifacts.
- If package installation changes global Python web dependencies, recreate a dedicated virtual environment and reinstall there.
- GitHub-hosted `windows-latest` runners are only used for unit tests, `doctor`, and MCP handshake smoke. Real Webots runtime smoke is exposed as a separate manual workflow for self-hosted Windows runners with Webots installed.
- Runtime-affecting changes now also path-trigger the self-hosted runtime workflow when the `webots` runner is available.
- `examples/` contains runnable demo assets; benchmark thresholds and pass/fail logic live in the benchmark registry inside the toolkit code.
- Wheel installs use bundled package-local scenario assets; source checkouts continue to use repo-local `examples/`.
