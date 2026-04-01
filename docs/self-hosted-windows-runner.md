# Self-Hosted Windows Runner

Use this when you want the `Windows Runtime Smoke` GitHub workflow to execute real Webots sessions.

## Required baseline

- Windows machine with Webots `R2025a`
- Python `3.11+`
- Repository checked out and installable with `pip install -e .[dev]`
- GitHub Actions self-hosted runner labeled `webots`

## Runner labels

Keep the runtime runner labels stable:

- `self-hosted`
- `windows`
- `webots`

The workflow file expects `runs-on: [self-hosted, windows, webots]`.

## Local readiness check

Run these commands on the runner host before trusting the workflow:

```powershell
webots-kit doctor --json
$env:WEBOTS_KIT_RUN_RUNTIME_SMOKE='1'
python -m pytest -q -k "session_start_inspect_stop_smoke or benchmark_smoke"
```

## Failure diagnosis

When a runtime smoke job fails, inspect:

- `session inspect --session <id>`
- `session logs --session <id>`
- uploaded diagnostics artifacts from the workflow

Canonical log names:

- `daemon.stdout.log`
- `daemon.stderr.log`
- `webots.stdout.log`
- `webots.stderr.log`
- `<robot-name>.stdout.log`
- `<robot-name>.stderr.log`
- `kit-supervisor.stdout.log`
- `kit-supervisor.stderr.log`

## Recommended progression

1. Keep using manual dispatch until the runner is stable.
2. Run the workflow repeatedly until runtime smoke is consistently green.
3. After stabilization, path-filtered `push` and `pull_request` triggers are expected for runtime-affecting changes.
