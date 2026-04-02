# Self-Hosted Windows Runner

Use this when you want the `Windows Runtime Smoke` GitHub workflow to execute real Webots sessions.

## Required baseline

- Windows machine with Webots `R2025a`
- Python `3.11+`
- runner-owned shared Python at `D:\actions-runner\python311-shared` as the machine standard
- Repository checked out and installable with `pip install -e .[dev]`
- GitHub Actions self-hosted runner labeled `interactive-webots`
- Runner launched from an interactive user session

## Runner labels

Keep the runtime runner labels stable:

- `self-hosted`
- `windows`
- `interactive-webots`

The workflow file expects `runs-on: [self-hosted, windows, interactive-webots]`.

## Why interactive mode matters

Webots runtime smoke is not supported from a Windows service session on this machine.
In service mode, Webots exits before controllers connect because the rendering stack cannot initialize a sufficient OpenGL context.
Use an interactive runner process in the logged-in desktop session instead.

## Local readiness check

Run these commands on the runner host before trusting the workflow:

```powershell
webots-kit doctor --json
$env:WEBOTS_KIT_RUN_RUNTIME_SMOKE='1'
python -m pytest -q -k "session_start_inspect_stop_smoke or benchmark_smoke or generated_scenario_smoke or imported_project_smoke"
```

The repository workflows treat `D:\actions-runner\python311-shared` as the machine-standard interpreter so the interactive runner and release smoke jobs do not depend on per-user PATH state.

## Failure diagnosis

When a runtime smoke job fails, inspect:

- `session inspect --session <id>`
- `session logs --session <id>`
- uploaded diagnostics artifacts from the workflow
- exported replay bundles when the failure path already produced `session export` artifacts

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
