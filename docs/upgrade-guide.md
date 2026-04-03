# Upgrade Guide

Use this page after upgrading the package or when you need a repeatable post-release verification lane for a team.

## Recommended Upgrade

```powershell
pipx upgrade webots-mcp-kit
```

Repo helper:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1 -Upgrade
```

## Post-Upgrade Verify

Quick path:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\verify_install.ps1
```

Runtime path:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\verify_install.ps1 -Runtime
```

Team-oriented upgrade lane:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\upgrade_check.ps1 -Workspace .\artifacts\upgrade-check -Runtime
```

That script verifies:

- public install verification
- bundled benchmark list
- line-follower starter controller validate
- controller-edit starter inspect/edit/validate
- world-edit starter validate/edit/validate
- import-replay starter import flow

## Rollback

If the new version does not pass your upgrade lane, reinstall the last known-good version:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1 -PackageSpec "webots-mcp-kit==<last-known-good>"
```

Then rerun:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\verify_install.ps1
```

## Notes

- GitHub-hosted Windows runners treat `verify_install.ps1 -Runtime` as a quick install check and skip the real benchmark branch
- real runtime proof still comes from local Windows or self-hosted `interactive-webots`

Next: use [Version policy](./version-policy.md) when you need to decide whether a CLI/MCP/schema change is stable or additive.
