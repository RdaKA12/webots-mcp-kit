# First Hour Guide

Use the supported `interactive-webots` runtime model below. There are two entry paths, but only one supported operational runtime path for real Webots execution.

## Path A: I want to connect an agent to Webots

### 1. Install

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install webots-mcp-kit
```

### 2. Verify runtime readiness

```powershell
webots-kit doctor --json
webots-kit benchmark list
```

You should confirm:

- `runtime_readiness.status` is `ready`
- `runtime_readiness.runner_label` is `interactive-webots`
- Webots `R2025a` is detected

The human-readable CLI outputs for `controller validate`, `benchmark report`, `scenario validate`, `scenario doctor`, and `session replay` all follow the same short-summary plus `next_step` style. Use the text output when you want a compact operator-facing readout, and `--json` when you want machine parsing.

### 3. Start a bundled session

```powershell
webots-kit session start --scenario line-follower --controller example --mode fast --render off
```

What a successful session looks like:

```json
{
  "session_id": "abc123def456",
  "status": "ready",
  "scenario": "line-follower",
  "target_robot_name": "epuck-line-follower"
}
```

### 4. Inspect state and capture a frame

```powershell
webots-kit session inspect --session <session-id>
webots-kit mcp serve
```

Expected first MCP flow:

1. `webots_session_start`
2. `webots_get_state`
3. `webots_get_sensors`
4. `webots_capture_camera`
5. `webots_session_stop`

### 5. Run a bundled benchmark

```powershell
webots-kit benchmark run line-follower --controller example --output .\report.json --duration-s 3
webots-kit benchmark report .\report.json
```

## Path B: I want to integrate my own controller

### 1. Scaffold from the closest scenario

```powershell
webots-kit controller scaffold .\controllers\my_agent.py --scenario line-follower
```

### 2. Keep the stable controller contract

- `ControllerAgent.from_robot(...)`
- `begin_step()`
- `report_step(...)`

### 3. Validate strictly

```powershell
webots-kit controller validate .\controllers\my_agent.py --scenario line-follower --strict --json
```

### 4. Benchmark it

```powershell
webots-kit benchmark run line-follower --controller .\controllers\my_agent.py --output .\report.json
```

### 5. Expose MCP if you want live agent control

```powershell
webots-kit mcp serve
```

## Notes

- Hosted GitHub Actions runners do not run full Webots runtime smoke.
- Real runtime smoke and real session execution require an `interactive-webots` self-hosted runner started from a logged-in desktop session.
- Windows service mode is not a supported runtime path for Webots session execution.
