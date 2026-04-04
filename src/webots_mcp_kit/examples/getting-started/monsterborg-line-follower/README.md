# MonsterBorg Line-Follower Starter

Use this starter when you want the shortest first-success path for the MonsterBorg Webots profile.

## Expected green path

```powershell
webots-kit controller validate .\controllers\demo_agent.py --scenario line-follower --robot-profile monsterborg-4wd --strict --json
webots-kit benchmark run line-follower --controller .\controllers\demo_agent.py --robot-profile monsterborg-4wd --output .\artifacts\monsterborg-line-follower-report.json --duration-s 8
webots-kit benchmark report .\artifacts\monsterborg-line-follower-report.json
```

Green condition:

- controller validation reports `valid: true`
- the MonsterBorg line-follower benchmark reports `pass: true`

Next:

- move to the MonsterBorg controller-edit starter if you want a structured edit loop
- move to the MonsterBorg world-edit starter if you want a first `.wbt` patch
