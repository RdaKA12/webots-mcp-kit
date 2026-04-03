# Line-Follower Starter

Use this starter when you want the fastest team-friendly path from a copied workspace to a green benchmark.

## Expected green path

```powershell
webots-kit controller validate .\controllers\demo_agent.py --scenario line-follower --strict --json
webots-kit benchmark run line-follower --controller .\controllers\demo_agent.py --output .\artifacts\line-follower-report.json --duration-s 3
webots-kit benchmark report .\artifacts\line-follower-report.json
```

Green condition:

- controller validation reports `valid: true`
- benchmark report shows `result: pass`

Next:

- move to the controller-edit starter if you want a structured edit loop
- move to the world-edit starter if you want to patch a `.wbt`
