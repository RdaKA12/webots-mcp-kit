# Self-Hosted Runner Maintenance

Use this checklist to keep the `interactive-webots` runner reliable.

## Baseline

- Windows updates controlled
- Webots `R2025a` pinned
- Python `3.11+`
- enough disk space for session artifacts and installer cache

## Routine checks

- `webots-kit doctor --json`
- local runtime smoke
- runner is started from an interactive user session
- service mode is disabled or excluded from runtime smoke labels
- cleanup of stale `LOCALAPPDATA\\webots-mcp-kit\\sessions`

## When changing runtime code

- run local runtime smoke before trusting workflow results
- confirm canonical logs still appear
- inspect artifact bundle generation path
