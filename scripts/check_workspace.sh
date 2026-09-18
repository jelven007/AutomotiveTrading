#!/usr/bin/env bash

set -uo pipefail

errors=0

pass() {
  printf 'PASS: %s\n' "$1"
}

fail() {
  printf 'FAIL: %s\n' "$1" >&2
  errors=$((errors + 1))
}

check_command() {
  local command_name=$1
  local display_name=$2

  if command -v "$command_name" >/dev/null 2>&1; then
    pass "$display_name is available"
  else
    fail "$display_name is not installed or not on PATH"
  fi
}

check_command python3 "Python"
check_command uv "uv"
check_command node "Node.js"
check_command pnpm "pnpm"
check_command docker "Docker"

if command -v uv >/dev/null 2>&1; then
  python_command=(uv run --no-sync python)
else
  python_command=(python3)
fi

if command -v "${python_command[0]}" >/dev/null 2>&1; then
  if "${python_command[@]}" -c 'import sys; raise SystemExit(sys.version_info[:2] != (3, 12))'; then
    pass "Python version is 3.12"
  else
    fail "Python 3.12 is required"
  fi
fi

if command -v docker >/dev/null 2>&1; then
  if docker compose version >/dev/null 2>&1; then
    pass "Docker Compose is available"
  else
    fail "Docker Compose plugin is not available"
  fi
fi

required_directories=(
  apps/web
  services
  packages/py-common
  packages/contracts
  packages/ts-api-client
  infra/compose
  infra/helm
  infra/terraform
  infra/observability
  tests/contract
  tests/integration
  tests/e2e
)

for directory in "${required_directories[@]}"; do
  if [[ -d "$directory" ]]; then
    pass "directory exists: $directory"
  else
    fail "missing directory: $directory"
  fi
done

required_files=(
  pyproject.toml
  pnpm-workspace.yaml
  package.json
  Makefile
)

for file in "${required_files[@]}"; do
  if [[ -f "$file" ]]; then
    pass "file exists: $file"
  else
    fail "missing file: $file"
  fi
done

if ((errors > 0)); then
  printf '\nWorkspace check failed with %d error(s).\n' "$errors" >&2
  exit 1
fi

printf '\nWorkspace check passed.\n'
