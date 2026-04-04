# MonsterBorg World-Edit Starter

Use this starter when you want a known-good MonsterBorg `.wbt` plus a first structured edit plan.

## Expected green path

```powershell
webots-kit world inspect .\worlds\editable_world.wbt --json
webots-kit world validate .\worlds\editable_world.wbt --json
webots-kit world edit .\worlds\editable_world.wbt --plan .\plans\world-edit.json --json
webots-kit world validate .\worlds\editable_world.wbt --json
```

Green condition:

- inspect reports `status: ready`
- validate reports `valid: true` before and after the edit
- edit returns `status: ready`

Next:

- run a MonsterBorg benchmark if you want runtime confirmation after the edit
