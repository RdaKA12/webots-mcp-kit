# Controller-Edit Starter

Use this starter when a team member wants a known-good controller file plus a first structured edit plan.

## Expected green path

```powershell
webots-kit controller inspect .\controllers\demo_agent.py --scenario line-follower --json
webots-kit controller edit .\controllers\demo_agent.py --plan .\plans\controller-edit.json --json
webots-kit controller validate .\controllers\demo_agent.py --scenario line-follower --strict --json
webots-kit benchmark run line-follower --controller .\controllers\demo_agent.py --output .\artifacts\controller-edit-report.json --duration-s 3
```

Green condition:

- inspect exposes editable regions
- edit applies cleanly
- strict validate passes
- benchmark still passes

Next:

- move to [team flows](../../../docs/team-flows.md) for the controller-author workflow
