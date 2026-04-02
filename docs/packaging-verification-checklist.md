# Packaging Verification Checklist

## Build

- `python -m build`
- `python -m twine check dist/*`

## Wheel smoke

- install the wheel into a clean venv
- run `webots-kit doctor --json`
- run `webots-kit benchmark list`
- run `webots-kit controller scaffold <path> --scenario line-follower`
- run `webots-kit project init <path>`
- run `webots-kit scenario init <path> --template epuck-waypoint`
- run `webots-kit scenario validate <spec-path>`
- run `webots-kit scenario build <spec-path>`
- or run the centralized flow:
  - `python scripts/clean_user_acceptance.py --workspace <path>`
- confirm bundled scenario assets resolve correctly

## Release smoke

- TestPyPI publish
- TestPyPI install smoke
- PyPI publish
- PyPI install smoke
- clean-venv acceptance should match the wheel smoke command flow above

## Failure hints

- missing bundled assets usually show up first in `benchmark list`
- metadata problems usually show up in `twine check`
- install issues should be reproduced from a clean venv, not an editable checkout
