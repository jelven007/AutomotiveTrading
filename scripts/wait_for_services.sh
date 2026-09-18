#!/usr/bin/env bash

set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
env_file=${QT_COMPOSE_ENV_FILE:-"$repo_root/infra/compose/.env"}

if [[ -f "$env_file" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$env_file"
  set +a
fi

wait_for_tcp() {
  local name=$1
  local port=$2
  local attempts=${3:-60}

  for ((attempt = 1; attempt <= attempts; attempt++)); do
    if (echo >/dev/tcp/127.0.0.1/"$port") >/dev/null 2>&1; then
      printf 'READY: %s on port %s\n' "$name" "$port"
      return 0
    fi
    sleep 2
  done

  printf 'TIMEOUT: %s on port %s\n' "$name" "$port" >&2
  return 1
}

wait_for_http() {
  local name=$1
  local url=$2
  local attempts=${3:-60}

  for ((attempt = 1; attempt <= attempts; attempt++)); do
    if curl --fail --silent --show-error "$url" >/dev/null 2>&1; then
      printf 'READY: %s at %s\n' "$name" "$url"
      return 0
    fi
    sleep 2
  done

  printf 'TIMEOUT: %s at %s\n' "$name" "$url" >&2
  return 1
}

wait_for_tcp "MySQL" "${QT_MYSQL_PORT:-3306}"
wait_for_tcp "Redis" "${QT_REDIS_PORT:-6379}"
wait_for_tcp "Kafka" "${QT_KAFKA_PORT:-9092}"
wait_for_http \
  "Schema Registry" \
  "http://127.0.0.1:${QT_SCHEMA_REGISTRY_PORT:-8081}/subjects"
wait_for_http "MinIO" "http://127.0.0.1:${QT_MINIO_PORT:-9000}/minio/health/live"
wait_for_http "Mailpit" "http://127.0.0.1:${QT_MAILPIT_PORT:-8025}/readyz"
