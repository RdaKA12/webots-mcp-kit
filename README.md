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

`v0.4.0`

Current focus:

- Windows-first local development
- Webots `R2025a`
- direct Webots integration without ROS2
- reusable controller-side integration through `ControllerAgent`
- benchmark registry with bundled example scenarios

## Bundled scenarios

- `line-follower`
  - camera-based line tracking
  - example world: `examples/line-follower`
- `obstacle-avoidance`
  - proximity-sensor obstacle avoidance
  - example world: `examples/obstacle-avoidance`

## Install

Use an isolated virtual environment. The toolkit depends on `mcp`, which may pull shared web stack packages into your global Python install.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e .[dev]
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
- `webots-kit controller validate <path> [--json]`
- `webots-kit mcp serve`

## Controller integration

The public controller-side entrypoint is `ControllerAgent`.

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

## Testing

Unit tests:

```powershell
python -m pytest -q
```

Full smoke tests with real Webots execution:

```powershell
$env:WEBOTS_KIT_RUN_SMOKE='1'
python -m pytest -q
```

## Troubleshooting

- If `doctor` fails, ensure `WEBOTS_HOME` is set or Webots is installed in `C:\Program Files\Webots`.
- If MCP or session startup closes immediately, inspect `session logs` for the session artifacts.
- If package installation changes global Python web dependencies, recreate a dedicated virtual environment and reinstall there.
