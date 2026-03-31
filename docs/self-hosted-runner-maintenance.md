# Self-Hosted Runner Maintenance

Use this checklist to keep the `webots` runner reliable.

## Baseline

- Windows updates controlled
- Webots `R2025a` pinned
- Python `3.11+`
- enough disk space for session artifacts and installer cache

## Routine checks

- `webots-kit doctor --json`
- local runtime smoke
- runner service account permissions
- cleanup of stale `LOCALAPPDATA\\webots-mcp-kit\\sessions`

## When changing runtime code

- run local runtime smoke before trusting workflow results
- confirm canonical logs still appear
- inspect artifact bundle generation path
