#!/usr/bin/env bash
set -euo pipefail

REPO_URL=""
RUNNER_TOKEN="${GITHUB_RUNNER_TOKEN:-}"
RUNNER_NAME="${HOSTNAME:-monsterborg-physical}"
RUNNER_DIR="${HOME}/actions-runner-monsterborg"
WORK_DIR="_work"
LABELS="monsterborg-physical"
RUNNER_VERSION="latest"
REPLACE_FLAG=""

usage() {
  cat <<'EOF'
Usage:
  scripts/setup_monsterborg_physical_runner.sh --repo-url <https://github.com/owner/repo> --token <runner-token> [options]

Options:
  --repo-url <url>        Repository URL for the self-hosted runner.
  --token <token>         Short-lived GitHub runner registration token.
  --runner-name <name>    Runner name. Default: <hostname>-monsterborg-physical
  --runner-dir <path>     Installation directory. Default: ~/actions-runner-monsterborg
  --work-dir <path>       Runner work directory. Default: _work
  --labels <labels>       Extra labels. Default: monsterborg-physical
  --runner-version <v>    Actions runner version or 'latest'. Default: latest
  --replace               Replace an existing runner registration with the same name.
  -h, --help              Show this help text.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo-url)
      REPO_URL="$2"
      shift 2
      ;;
    --token)
      RUNNER_TOKEN="$2"
      shift 2
      ;;
    --runner-name)
      RUNNER_NAME="$2"
      shift 2
      ;;
    --runner-dir)
      RUNNER_DIR="$2"
      shift 2
      ;;
    --work-dir)
      WORK_DIR="$2"
      shift 2
      ;;
    --labels)
      LABELS="$2"
      shift 2
      ;;
    --runner-version)
      RUNNER_VERSION="$2"
      shift 2
      ;;
    --replace)
      REPLACE_FLAG="--replace"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ -z "${REPO_URL}" || -z "${RUNNER_TOKEN}" ]]; then
  echo "Both --repo-url and --token are required." >&2
  usage
  exit 1
fi

ARCH="$(uname -m)"
case "${ARCH}" in
  aarch64|arm64)
    RUNNER_ARCH="arm64"
    ;;
  armv7l|armv6l)
    RUNNER_ARCH="arm"
    ;;
  x86_64)
    RUNNER_ARCH="x64"
    ;;
  *)
    echo "Unsupported architecture: ${ARCH}" >&2
    exit 1
    ;;
esac

if [[ "${RUNNER_VERSION}" == "latest" ]]; then
  RUNNER_VERSION="$(python3 - <<'PY'
import json
import urllib.request

with urllib.request.urlopen("https://api.github.com/repos/actions/runner/releases/latest") as response:
    payload = json.load(response)
print(str(payload["tag_name"]).lstrip("v"))
PY
)"
fi

RUNNER_PKG="actions-runner-linux-${RUNNER_ARCH}-${RUNNER_VERSION}.tar.gz"
RUNNER_URL="https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/${RUNNER_PKG}"
FULL_RUNNER_NAME="${RUNNER_NAME}-monsterborg-physical"
FULL_LABELS="${LABELS}"

mkdir -p "${RUNNER_DIR}"
cd "${RUNNER_DIR}"

if [[ ! -f ".runner" ]]; then
  rm -f "${RUNNER_PKG}"
  echo "Downloading ${RUNNER_URL}"
  curl -fsSL "${RUNNER_URL}" -o "${RUNNER_PKG}"
  tar xzf "${RUNNER_PKG}"
fi

./config.sh \
  --url "${REPO_URL}" \
  --token "${RUNNER_TOKEN}" \
  --name "${FULL_RUNNER_NAME}" \
  --labels "${FULL_LABELS}" \
  --work "${WORK_DIR}" \
  --unattended \
  ${REPLACE_FLAG}

if [[ -x "./svc.sh" ]]; then
  sudo ./svc.sh install "${USER}"
  sudo ./svc.sh start
fi

cat <<EOF
MonsterBorg physical runner configured.

Runner directory: ${RUNNER_DIR}
Runner name: ${FULL_RUNNER_NAME}
Labels: self-hosted, linux, ${FULL_LABELS}

Local verification:
  python3 scripts/monsterborg_physical_verify.py --json
  python3 -m pytest -q tests/test_monsterborg_physical_gate.py
EOF
