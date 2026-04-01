# First Hour Guide

This is the shortest supported path for a new user.

## 1. Install

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install webots-mcp-kit
```

## 2. Verify the environment

```powershell
webots-kit doctor --json
webots-kit benchmark list
```

You should see:

- Webots `R2025a`
- a valid `WEBOTS_HOME` or default install detection
- bundled scenarios in `benchmark list`

## 3. Run a bundled benchmark

```powershell
webots-kit benchmark run line-follower --controller example --output .\report.json --duration-s 3
webots-kit benchmark report .\report.json
```

## 4. Start your own controller

```powershell
webots-kit controller scaffold .\controllers\my_agent.py --scenario line-follower
webots-kit controller validate .\controllers\my_agent.py --scenario line-follower --strict --json
```

## 5. Expose MCP tools

```powershell
webots-kit mcp serve
```

## Notes

- Hosted GitHub Actions runners do not run full runtime smoke.
- Full session and benchmark smoke require either a local machine or a self-hosted Windows runner with Webots installed.
