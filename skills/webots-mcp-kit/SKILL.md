---
name: webots-mcp-kit
description: Use when working on Webots controllers, running the bundled line follower benchmark, debugging sensors or camera data, or observing a Webots simulation through webots-mcp-kit MCP tools.
---

# Webots MCP Kit

Use this skill for Webots controller work, benchmark-driven debugging, or simulation observation through MCP.
This toolkit is general developer tooling; the bundled line follower is only the first reference scenario.

## Standard workflow

1. Run `webots-kit doctor` first.
2. Run `webots-kit benchmark list` and choose a scenario.
3. Run `webots-kit benchmark run <scenario> --controller <path-or-id> --output <report.json>`.
4. If interactive inspection is needed, run `webots-kit session start ...` or `webots-kit mcp serve`.
5. Use `webots-kit controller validate <path>` and `webots-kit session logs --session <id>` before changing controller logic.

## Notes

- Full camera and sensor tooling require a controller that imports `webots_mcp_kit.agent`.
- The public controller-side wrapper is `ControllerAgent`.
- Bundled scenarios live under `examples/`.
