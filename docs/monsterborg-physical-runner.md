# MonsterBorg Physical Runner

Use this page when you want to add the designated Raspberry Pi self-hosted runner that the stable MonsterBorg physical gate expects.

Important scope note:

- this is not general Linux runtime support
- this runner exists only for the `monsterborg-physical` release gate
- normal Webots runtime support remains Windows + `interactive-webots`

## Required labels

The release and smoke workflows expect:

- `self-hosted`
- `linux`
- `monsterborg-physical`

## Required machine baseline

- Raspberry Pi host for the physical MonsterBorg lane
- Python `3.11+`
- Git
- outbound network access to GitHub
- MonsterBorg physical adapter dependencies:
  - `ThunderBorg3`
  - `smbus2`
  - `picamera2` when camera capture is required

## One-time GitHub step

In the repo settings:

1. Open `Settings -> Actions -> Runners`
2. Click `New self-hosted runner`
3. Choose `Linux`
4. Choose the correct architecture for the Pi
5. Copy the temporary runner token

That token is short-lived and is required by the setup script below.

## One-command setup on the Pi

From a checkout of this repo on the Raspberry Pi:

```bash
chmod +x ./scripts/setup_monsterborg_physical_runner.sh
./scripts/setup_monsterborg_physical_runner.sh \
  --repo-url https://github.com/RdaKA12/webots-mcp-kit \
  --token <RUNNER_TOKEN> \
  --runner-name monsterborg-pi \
  --replace
```

What the script does:

- detects the Pi architecture
- downloads the correct GitHub Actions runner package
- registers the runner with `monsterborg-physical`
- installs and starts the runner service when `svc.sh` is available

## Verify the runner host

Run these directly on the Pi:

```bash
python3 scripts/monsterborg_physical_verify.py --json
python3 -m pytest -q tests/test_monsterborg_physical_gate.py
```

Green condition:

- physical verify returns `status: ready`
- `tests/test_monsterborg_physical_gate.py` passes

## How the release gate uses it

- preview tags like `v2.9.0-alpha.N` skip the physical gate
- stable tags like `v2.9.0` require this runner only when the repository variable `MONSTERBORG_PHYSICAL_GATE=enabled` is set
- until that variable is enabled, the physical workflow is manual-only through `workflow_dispatch`

The workflow files involved are:

- [monsterborg-physical-smoke.yml](../.github/workflows/monsterborg-physical-smoke.yml)
- [release.yml](../.github/workflows/release.yml)

## Troubleshooting

If the job stays queued:

- confirm the runner is online in GitHub
- confirm the labels include `monsterborg-physical`
- confirm the machine is actually Linux, not the Windows Webots runner
- confirm the runner service is running on the Pi

Next: continue with [MonsterBorg physical adapter](./monsterborg-physical-adapter.md) for capture/export/replay and calibration flow.
