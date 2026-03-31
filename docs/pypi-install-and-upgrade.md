# PyPI Install and Upgrade

## Install

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install webots-mcp-kit
```

## Verify

```powershell
webots-kit doctor --json
webots-kit benchmark list
```

## Upgrade

```powershell
pip install --upgrade webots-mcp-kit
```

## Notes

- The package is Windows-first and assumes Webots `R2025a`.
- If `doctor` fails after upgrade, verify `WEBOTS_HOME` and the active Python environment.
- Bundled benchmark assets are shipped inside the wheel, so `benchmark list` should work without a source checkout.
