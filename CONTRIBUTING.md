# Contributing

## Development setup

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e .[dev]
```

Webots should be installed in `C:\Program Files\Webots` or exposed through `WEBOTS_HOME`.

## Before opening a pull request

Run:

```powershell
python -m pytest -q
webots-kit doctor
webots-kit benchmark list
webots-kit project init .\scratch-project
python -m build
python -m twine check dist/*
```

For full smoke validation:

```powershell
$env:WEBOTS_KIT_RUN_SMOKE='1'
python -m pytest -q -k mcp_tool_list_smoke
$env:WEBOTS_KIT_RUN_RUNTIME_SMOKE='1'
python -m pytest -q -k "session_start_inspect_stop_smoke or benchmark_smoke"
```

## Coding notes

- Keep CLI command names stable.
- Keep MCP tool names stable unless there is a strong compatibility reason.
- Prefer adding new scenario/example directories instead of overloading the line follower example.
- Treat `ControllerAgent` as the public controller SDK surface.
- Use `webots-kit controller scaffold` when starting a new bundled-scenario controller.
- Use `webots-kit scenario init` and `webots-kit scenario build` for template-driven zero-to-sim work instead of hand-rolling new project skeletons.
- Keep the self-hosted Windows runtime runner label as `interactive-webots`.
- Run runtime smoke from an interactive user session; do not rely on a Windows service runner for Webots execution.
- `examples/` are demo assets; benchmark thresholds belong in the scenario registry.
- Bundled runtime assets that must ship in wheels live under `src/webots_mcp_kit/examples/`.
- Keep `Packaging CI` green before tagging a release.
- Changes to `daemon.py`, `launcher.py`, `runtime/**`, bundled package examples, `benchmarks.py`, `scenario_ops.py`, or `tests/test_smoke_cli.py` are considered runtime-affecting and should be reviewed against the self-hosted runtime workflow.
