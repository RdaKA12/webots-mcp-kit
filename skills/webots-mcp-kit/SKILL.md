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
3. For a custom controller, start from `webots-kit controller scaffold <path> --scenario <name>`.
4. Run `webots-kit controller validate <path> --scenario <name> [--strict]`.
5. Run `webots-kit benchmark run <scenario> --controller <path-or-id> --output <report.json>`.
6. If interactive inspection is needed, run `webots-kit session start ...` or `webots-kit mcp serve`.
7. Use `webots-kit session logs --session <id>` before changing controller logic.

## Notes

- Full camera and sensor tooling require a controller that imports `webots_mcp_kit.agent`.
- The stable public controller-side wrapper is `ControllerAgent`.
- The supported public API is `ControllerAgent.from_robot(...)`, `begin_step()`, and `report_step(...)`.
- Bundled scenarios live under `examples/`.
- `examples/` are runnable demos. Benchmark thresholds and pass/fail rules come from the toolkit registry.
