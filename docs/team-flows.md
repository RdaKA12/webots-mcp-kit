# Team Flows

Use this page when the toolkit is being repeated by more than one developer and you want a fixed, documented path.

Robot profiles:

- `e-puck`: stable baseline
- `monsterborg-4wd`: Webots and physical-adapter lane

## Evaluator Flow

Use this when a new teammate is only trying to get to the first green benchmark.

Starter workspace:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\bootstrap_workspace.ps1 -Starter line-follower -Destination .\workspaces\line-follower-demo
```

Commands:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\verify_install.ps1 -Runtime
webots-kit controller validate .\workspaces\line-follower-demo\controllers\demo_agent.py --scenario line-follower --strict --json
webots-kit benchmark run line-follower --controller .\workspaces\line-follower-demo\controllers\demo_agent.py --output .\workspaces\line-follower-demo\artifacts\line-follower-report.json --duration-s 3
webots-kit benchmark report .\workspaces\line-follower-demo\artifacts\line-follower-report.json
```

Green condition:

- verify passes
- strict controller validate passes
- benchmark report shows pass

MonsterBorg variant:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\bootstrap_workspace.ps1 -Starter monsterborg-line-follower -Destination .\workspaces\monsterborg-line-follower
powershell -ExecutionPolicy Bypass -File .\scripts\verify_install.ps1 -RobotProfile monsterborg-4wd -Runtime
webots-kit controller validate .\workspaces\monsterborg-line-follower\controllers\demo_agent.py --scenario line-follower --robot-profile monsterborg-4wd --strict --json
webots-kit benchmark run line-follower --controller .\workspaces\monsterborg-line-follower\controllers\demo_agent.py --robot-profile monsterborg-4wd --output .\workspaces\monsterborg-line-follower\artifacts\report.json --duration-s 8
```

## Controller Author Flow

Use this when a teammate is writing or safely patching controller code.

Starter workspace:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\bootstrap_workspace.ps1 -Starter controller-edit -Destination .\workspaces\controller-edit-demo
```

Commands:

```powershell
webots-kit controller inspect .\workspaces\controller-edit-demo\controllers\demo_agent.py --scenario line-follower --json
webots-kit controller edit .\workspaces\controller-edit-demo\controllers\demo_agent.py --plan .\workspaces\controller-edit-demo\plans\controller-edit.json --json
webots-kit controller validate .\workspaces\controller-edit-demo\controllers\demo_agent.py --scenario line-follower --strict --json
webots-kit benchmark run line-follower --controller .\workspaces\controller-edit-demo\controllers\demo_agent.py --output .\workspaces\controller-edit-demo\artifacts\controller-edit-report.json --duration-s 3
```

Green condition:

- inspect reports editable regions
- edit applies with `status: ready`
- strict validate passes
- benchmark still passes

## World Author Flow

Use this when a teammate is patching an existing `.wbt` or validating a new task-world shape.

Starter workspace:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\bootstrap_workspace.ps1 -Starter world-edit -Destination .\workspaces\world-edit-demo
```

Commands:

```powershell
webots-kit world inspect .\workspaces\world-edit-demo\worlds\editable_world.wbt --json
webots-kit world validate .\workspaces\world-edit-demo\worlds\editable_world.wbt --json
webots-kit world edit .\workspaces\world-edit-demo\worlds\editable_world.wbt --plan .\workspaces\world-edit-demo\plans\world-edit.json --json
webots-kit world validate .\workspaces\world-edit-demo\worlds\editable_world.wbt --json
```

Green condition:

- inspect reports `status: ready`
- validate passes before and after the edit
- edit returns `status: ready`

## Importer / Triage Flow

Use this when the team already has a world/controller pair and wants kit-managed metadata plus replay-ready handoff.

Starter workspace:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\bootstrap_workspace.ps1 -Starter import-replay -Destination .\workspaces\import-replay-demo
```

Commands:

```powershell
webots-kit project import --world .\workspaces\import-replay-demo\worlds\import_world.wbt --controller .\workspaces\import-replay-demo\controllers\import_agent.py --project-root .\workspaces\import-replay-demo\imported-project
```

Optional runtime follow-up:

```powershell
webots-kit session start --scenario line-follower --world .\workspaces\import-replay-demo\worlds\import_world.wbt --controller .\workspaces\import-replay-demo\controllers\import_agent.py --mode fast --render off
webots-kit session export <session-id> --output .\workspaces\import-replay-demo\artifacts\exports\<session-id>
webots-kit session replay .\workspaces\import-replay-demo\artifacts\exports\<session-id>
```

Green condition:

- import writes project and imported scenario metadata
- replay later produces a readable triage summary

Next: use [Upgrade guide](./upgrade-guide.md) when you need the repeatable post-upgrade verification lane.
