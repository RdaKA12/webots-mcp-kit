# webots-mcp-kit

`webots-mcp-kit` is a local-first toolkit for connecting LLM agents to Webots.
It ships three pieces together:

- a pip-installable CLI and MCP server
- a small controller helper SDK for agent-aware Webots controllers
- a deterministic line-follower benchmark workflow

The bundled line follower is only the first example and benchmark scenario.
The session launcher, agent SDK, and MCP tools are intended to be generic for other Webots robots and worlds.

## Current v0.1 scope

- Windows-first
- Webots `R2025a`
- direct Webots integration, no ROS2 dependency
- example world and controller under `examples/line-follower`

## Install

```powershell
pip install -e .[dev]
```

## Quick start

```powershell
webots-kit doctor
webots-kit benchmark run line-follower --controller example --output .\report.json
webots-kit benchmark report .\report.json
```

To run the MCP server:

```powershell
webots-kit mcp serve
```

## CLI

- `webots-kit doctor`
- `webots-kit session start --world <path> [--mode fast|realtime|pause] [--render on|off]`
- `webots-kit session stop --session <id>`
- `webots-kit benchmark run line-follower --controller <path-or-id> --output <report.json>`
- `webots-kit benchmark report <report.json>`
- `webots-kit mcp serve`

## Notes

- Full sensor and camera tooling requires a controller that imports `webots_mcp_kit.agent`.
- The example benchmark world uses extern controllers for both the robot and a supervisor runtime.
- `pause/resume` in v0.1 is implemented as controller pause for deterministic agent debugging, not a hard Webots GUI pause.
