# Packaging Verification Checklist

## Build

- `python -m build`
- `python -m twine check dist/*`

## Wheel smoke

- install the wheel into a clean venv
- run `webots-kit benchmark list`
- confirm bundled scenario assets resolve correctly

## Release smoke

- TestPyPI publish
- TestPyPI install smoke
- PyPI publish
- PyPI install smoke

## Failure hints

- missing bundled assets usually show up first in `benchmark list`
- metadata problems usually show up in `twine check`
- install issues should be reproduced from a clean venv, not an editable checkout
