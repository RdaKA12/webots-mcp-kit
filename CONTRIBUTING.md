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
- Keep the self-hosted Windows runner label as `webots`.
- `examples/` are demo assets; benchmark thresholds belong in the scenario registry.
