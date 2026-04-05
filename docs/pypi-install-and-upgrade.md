# PyPI Install and Upgrade

Use this page when you need the package-install reference. For the shortest first-success path, use [First hour guide](./first-hour-guide.md).

## Recommended Install Path

```powershell
pipx install webots-mcp-kit
```

From a repo checkout, the helper script drives the same public install story:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1
```

## Verify The Install

Quick verification:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\verify_install.ps1
```

Runtime verification:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\verify_install.ps1 -Runtime
```

## Upgrade

Direct upgrade:

```powershell
pipx upgrade webots-mcp-kit
```

Repo helper:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1 -Upgrade
```

Team-oriented upgrade lane:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\upgrade_check.ps1 -Workspace .\artifacts\upgrade-check -Runtime
```

MonsterBorg team upgrade lane:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\upgrade_check.ps1 -Workspace .\artifacts\monsterborg-upgrade-check -RobotProfile monsterborg-4wd -Runtime
```

Starter workspace bootstrap:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\bootstrap_workspace.ps1 -Starter line-follower -Destination .\workspaces\line-follower-demo
```

MonsterBorg starter bootstrap:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\bootstrap_workspace.ps1 -Starter monsterborg-line-follower -Destination .\workspaces\monsterborg-line-follower
```

## Install A Specific Version Or Wheel

Pinned PyPI version:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1 -PackageSpec "webots-mcp-kit==2.9.0a1"
```

Local wheel:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1 -PackageSpec ".\dist\webots_mcp_kit-2.9.0a1-py3-none-any.whl"
```

## Fallback: Virtual Environment

Use this only when `pipx` is not appropriate for your machine or workflow:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install webots-mcp-kit
```

Then run:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\verify_install.ps1
```

## Notes

- Supported baseline: Windows, Webots `R2025a`, Python `3.11+`, `interactive-webots`, `e-puck`, `monsterborg-4wd`
- The install helpers do not silently mutate persistent `WEBOTS_HOME`
- Bundled benchmark assets ship inside the wheel, so `benchmark list` and bundled-world inspect work without a source checkout
- If install or verify fails, go to [Troubleshooting](./troubleshooting.md)
- Use [Upgrade guide](./upgrade-guide.md) for the repeatable post-upgrade verification lane
- Use [Version policy](./version-policy.md) when deciding which surfaces are stable versus additive

Next: continue with [First hour guide](./first-hour-guide.md).
