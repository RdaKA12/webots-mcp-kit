---
name: webots-mcp-kit
description: Use when working on Webots controllers, running the bundled line follower benchmark, debugging sensors or camera data, or observing a Webots simulation through webots-mcp-kit MCP tools.
---

# Webots MCP Kit

Use this skill for Webots controller work, benchmark-driven debugging, or simulation observation through MCP.

## Standard workflow

1. Run `webots-kit doctor` first.
2. Run `webots-kit benchmark run line-follower --controller <path-or-id> --output <report.json>`.
3. If interactive inspection is needed, run `webots-kit mcp serve`.
4. Use the report and session logs before changing controller logic.

## Notes

- Full camera and sensor tooling require a controller that imports `webots_mcp_kit.agent`.
- The bundled world is `examples/line-follower/worlds/line_follower_benchmark.wbt`.
- The bundled controller is `examples/line-follower/controllers/line_follower_agent.py`.
