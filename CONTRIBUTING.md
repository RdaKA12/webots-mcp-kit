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
```

For full smoke validation:

```powershell
$env:WEBOTS_KIT_RUN_SMOKE='1'
python -m pytest -q
```

## Coding notes

- Keep CLI command names stable.
- Keep MCP tool names stable unless there is a strong compatibility reason.
- Prefer adding new scenario/example directories instead of overloading the line follower example.
- Treat `ControllerAgent` as the public controller SDK surface.
