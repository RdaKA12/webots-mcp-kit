# MonsterBorg Controller-Edit Starter

Use this starter when you want a known-good MonsterBorg controller plus a first structured edit plan.

## Expected green path

```powershell
webots-kit controller inspect .\controllers\demo_agent.py --scenario line-follower --robot-profile monsterborg-4wd --json
webots-kit controller edit .\controllers\demo_agent.py --plan .\plans\controller-edit.json --robot-profile monsterborg-4wd --json
webots-kit controller validate .\controllers\demo_agent.py --scenario line-follower --robot-profile monsterborg-4wd --strict --json
webots-kit benchmark run line-follower --controller .\controllers\demo_agent.py --robot-profile monsterborg-4wd --output .\artifacts\monsterborg-controller-edit-report.json --duration-s 8
```

Green condition:

- inspect/edit/validate all return clean JSON
- the edited controller still passes the MonsterBorg benchmark

Next:

- use the full controller authoring guide for larger edits
