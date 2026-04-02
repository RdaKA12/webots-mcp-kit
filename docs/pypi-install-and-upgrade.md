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
webots-kit controller scaffold .\controllers\demo_agent.py --scenario line-follower
webots-kit controller validate .\controllers\demo_agent.py --scenario line-follower
webots-kit project init .\my-webots-project
webots-kit scenario init .\my-webots-project\scenarios\demo-waypoint --template epuck-waypoint
webots-kit scenario validate .\my-webots-project\scenarios\demo-waypoint\webots-kit.scenario.json
webots-kit scenario build .\my-webots-project\scenarios\demo-waypoint\webots-kit.scenario.json
```

## Upgrade

```powershell
pip install --upgrade webots-mcp-kit
```

## Notes

- The package is Windows-first and assumes Webots `R2025a`.
- If `doctor` fails after upgrade, verify `WEBOTS_HOME` and the active Python environment.
- Bundled benchmark assets are shipped inside the wheel, so `benchmark list` should work without a source checkout.
- `controller scaffold`, `controller validate`, `project import`, and `mcp serve` are also supported from a PyPI install.
