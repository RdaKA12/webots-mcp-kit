# Import-And-Replay Starter

Use this starter when the team already has a world/controller pair and wants a repeatable import + replay handoff flow.

## Expected green path

```powershell
webots-kit project import --world .\worlds\import_world.wbt --controller .\controllers\import_agent.py --project-root .\imported-project
```

Optional runtime follow-up:

```powershell
webots-kit session start --scenario line-follower --world .\worlds\import_world.wbt --controller .\controllers\import_agent.py --mode fast --render off
webots-kit session export <session-id> --output .\artifacts\exports\<session-id>
webots-kit session replay .\artifacts\exports\<session-id>
```

Green condition:

- import writes `webots-kit.project.json` and an imported scenario spec
- replay gives a readable triage summary after export

Next:

- use [Project import and session replay](../../../docs/project-import-and-replay.md) for the full handoff flow
