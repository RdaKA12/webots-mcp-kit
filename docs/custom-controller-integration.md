# Custom Controller Integration

Use this flow when the controller lives outside the bundled examples.

## Supported contract

The supported public API is:

- `ControllerAgent.from_robot(...)`
- `begin_step()`
- `report_step(...)`

Required behavior:

- create a `Robot()` instance
- run a `robot.step(...)` loop
- call `begin_step()` at each step
- publish `sensors`, `metrics`, and `actuators` through `report_step(...)`

For bundled scenarios, camera support is expected through `default_camera="camera"`.

## Recommended flow

### 1. Scaffold from the closest bundled scenario

```powershell
webots-kit controller scaffold .\controllers\my_agent.py --scenario line-follower
```

### 2. Integrate your own logic without changing the agent contract

```python
from controller import Robot
from webots_mcp_kit.agent import ControllerAgent

robot = Robot()
agent = ControllerAgent.from_robot(robot, default_camera="camera")

while robot.step(int(robot.getBasicTimeStep())) != -1:
    override = agent.begin_step()
    agent.report_step(
        sensors={},
        metrics={},
        actuators={},
        camera_frames=None,
    )
```

### 3. Validate

Quick validation:

```powershell
webots-kit controller validate .\controllers\my_agent.py --scenario line-follower
```

Release-grade validation:

```powershell
webots-kit controller validate .\controllers\my_agent.py --scenario line-follower --strict --json
```

### 4. Benchmark

```powershell
webots-kit benchmark run line-follower --controller .\controllers\my_agent.py --output .\report.json
webots-kit benchmark report .\report.json
```

### 5. Use MCP for live inspection

```powershell
webots-kit mcp serve
```

Recommended first tools:

- `webots_session_start`
- `webots_get_state`
- `webots_get_sensors`
- `webots_capture_camera`
- `webots_session_stop`

## Notes

- This flow is supported from both a source checkout and a PyPI install.
- `--strict` is meant for release-grade validation, not early sketches.
- If validation passes but runtime still fails, inspect `session inspect` and `session logs` before changing the controller contract.
