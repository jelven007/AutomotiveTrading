#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${QT_DEPLOY_ENV_FILE:-${ROOT_DIR}/infra/compose/.env.deploy}"
COMPOSE_FILE="${ROOT_DIR}/infra/compose/docker-compose.yml"

usage() {
  cat <<'EOF'
用法：bash scripts/deploy.sh <命令>

命令：
  init      生成部署环境文件
  up        构建、迁移并启动完整系统
  status    查看容器状态
  logs      查看日志，可追加服务名
  restart   重启 Identity、Trading 和 Web
  down      停止服务并保留 MySQL 数据
  help      显示帮助
EOF
}

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "缺少命令：$1" >&2
    exit 1
  fi
}

fernet_key() {
  openssl rand -base64 32 | tr "+/" "-_" | tr -d "\n"
}

init_env() {
  require_command openssl
  if [[ -e "${ENV_FILE}" ]]; then
    chmod 600 "${ENV_FILE}"
    echo "部署配置已存在，未覆盖：${ENV_FILE}"
    return
  fi

  mkdir -p "$(dirname "${ENV_FILE}")"
  umask 077
  cat >"${ENV_FILE}" <<EOF
# 由 scripts/deploy.sh init 生成，请勿提交到 Git。
MYSQL_ROOT_PASSWORD=$(openssl rand -hex 24)
MYSQL_USER=qt_app
MYSQL_PASSWORD=$(openssl rand -hex 24)

AUTH_JWT_SECRET=$(openssl rand -hex 48)
AUTH_TOTP_ENCRYPTION_KEY=$(fernet_key)

ENVIRONMENT=production
SINGLE_OWNER_MODE=true
QT_BIND_HOST=127.0.0.1
MYSQL_PORT=3306
IDENTITY_PORT=8001
TRADING_PORT=8004
WEB_BIND_HOST=0.0.0.0
WEB_PORT=8080

BINANCE_CREDENTIAL_MASTER_KEY_FILE=/opt/quant-trading/secrets/credential-master-key
BINANCE_CREDENTIAL_MASTER_KEY_UID=100
BINANCE_ENVIRONMENT=demo
DEMO_TRADING_ENABLED=false
PUBLIC_BASE_URL=
EOF
  chmod 600 "${ENV_FILE}"
  echo "已生成部署配置：${ENV_FILE}"
}

env_value() {
  sed -n "s/^$1=//p" "${ENV_FILE}" | tail -n 1
}

file_mode() {
  if stat -f "%Lp" "$1" >/dev/null 2>&1; then
    stat -f "%Lp" "$1"
  else
    stat -c "%a" "$1"
  fi
}

file_owner_uid() {
  if stat -f "%u" "$1" >/dev/null 2>&1; then
    stat -f "%u" "$1"
  else
    stat -c "%u" "$1"
  fi
}

require_deployment() {
  if [[ ! -f "${ENV_FILE}" ]]; then
    echo "部署配置不存在，请先执行：bash scripts/deploy.sh init" >&2
    exit 1
  fi
  if grep -q "please-change" "${ENV_FILE}"; then
    echo "部署配置仍包含 please-change 占位值。" >&2
    exit 1
  fi
}

require_compose() {
  require_command docker
  docker compose version >/dev/null
}

require_binance_configuration() {
  local expected_uid key_path key_size mode owner_uid
  key_path="$(env_value BINANCE_CREDENTIAL_MASTER_KEY_FILE)"
  key_path="${key_path:-/opt/quant-trading/secrets/credential-master-key}"
  expected_uid="$(env_value BINANCE_CREDENTIAL_MASTER_KEY_UID)"
  expected_uid="${expected_uid:-100}"

  if [[ ! -f "${key_path}" ]]; then
    echo "B 凭据主密钥不存在：${key_path}" >&2
    return 1
  fi
  mode="$(file_mode "${key_path}")"
  key_size="$(wc -c <"${key_path}" | tr -d "[:space:]")"
  owner_uid="$(file_owner_uid "${key_path}")"
  if [[ "${mode}" != "600" ]]; then
    echo "B 凭据主密钥权限必须为 600，当前为 ${mode}。" >&2
    return 1
  fi
  if [[ "${key_size}" != "32" ]]; then
    echo "B 凭据主密钥必须恰好为 32 个原始字节。" >&2
    return 1
  fi
  if [[ "${owner_uid}" != "${expected_uid}" ]]; then
    echo "B 凭据主密钥所有者必须为 Trading UID ${expected_uid}。" >&2
    return 1
  fi
  if [[ "$(env_value BINANCE_ENVIRONMENT)" != "demo" ]]; then
    echo "当前版本要求 BINANCE_ENVIRONMENT=demo，禁止连接主网。" >&2
    return 1
  fi
  if [[ "$(env_value DEMO_TRADING_ENABLED)" != "false" ]]; then
    echo "下单接口完成前要求 DEMO_TRADING_ENABLED=false。" >&2
    return 1
  fi
  if [[ "$(env_value SINGLE_OWNER_MODE)" != "true" ]]; then
    echo "生产环境要求 SINGLE_OWNER_MODE=true。" >&2
    return 1
  fi
  if [[ "$(env_value PUBLIC_BASE_URL)" != https://* ]]; then
    echo "PUBLIC_BASE_URL 必须使用可信 HTTPS 地址。" >&2
    return 1
  fi
}

compose_cmd() {
  docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" "$@"
}

wait_for_jobs() {
  local jobs=(database-init identity-migrate trading-migrate)
  local deadline=$((SECONDS + ${QT_DEPLOY_WAIT_SECONDS:-300}))
  local container_id exit_code job pending state

  while ((SECONDS < deadline)); do
    pending=""
    for job in "${jobs[@]}"; do
      container_id="$(compose_cmd ps -a -q "${job}")"
      state="$(docker inspect --format '{{.State.Status}}' "${container_id}")"
      if [[ "${state}" == "exited" ]]; then
        exit_code="$(docker inspect --format '{{.State.ExitCode}}' "${container_id}")"
        if [[ "${exit_code}" == "0" ]]; then
          continue
        fi
        echo "迁移任务失败：${job}（exit=${exit_code}）" >&2
        compose_cmd logs --tail=100 "${job}" >&2
        return 1
      fi
      pending="${pending} ${job}(${state})"
    done
    if [[ -z "${pending}" ]]; then
      return
    fi
    echo "等待迁移任务：${pending# }"
    sleep 2
  done
  echo "等待迁移任务超时。" >&2
  return 1
}

wait_for_services() {
  local services=(mysql identity-tenant trading web)
  local deadline=$((SECONDS + ${QT_DEPLOY_WAIT_SECONDS:-300}))
  local container_id health pending service state

  while ((SECONDS < deadline)); do
    pending=""
    for service in "${services[@]}"; do
      container_id="$(compose_cmd ps -a -q "${service}")"
      state="$(docker inspect --format '{{.State.Status}}' "${container_id}")"
      health="$(
        docker inspect \
          --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' \
          "${container_id}"
      )"
      if [[ "${state}" == "running" && "${health}" =~ ^(healthy|none)$ ]]; then
        continue
      fi
      if [[ "${state}" =~ ^(dead|exited)$ || "${health}" == "unhealthy" ]]; then
        echo "服务启动失败：${service}（state=${state}, health=${health}）" >&2
        compose_cmd logs --tail=100 "${service}" >&2
        return 1
      fi
      pending="${pending} ${service}(${health})"
    done
    if [[ -z "${pending}" ]]; then
      return
    fi
    echo "等待服务健康：${pending# }"
    sleep 3
  done
  echo "等待服务健康超时。" >&2
  return 1
}

command="${1:-help}"
case "${command}" in
  init)
    init_env
    ;;
  up)
    require_deployment
    require_binance_configuration
    require_compose
    compose_cmd config --quiet
    compose_cmd up -d --build --remove-orphans
    wait_for_jobs
    wait_for_services
    echo "部署完成：$(env_value PUBLIC_BASE_URL)"
    compose_cmd ps -a
    ;;
  status)
    require_deployment
    require_compose
    compose_cmd ps -a
    ;;
  logs)
    require_deployment
    require_compose
    shift
    compose_cmd logs --tail=200 -f "$@"
    ;;
  restart)
    require_deployment
    require_compose
    compose_cmd restart identity-tenant trading web
    compose_cmd ps -a
    ;;
  down)
    require_deployment
    require_compose
    compose_cmd down
    ;;
  help | --help | -h)
    usage
    ;;
  *)
    echo "未知命令：${command}" >&2
    usage >&2
    exit 2
    ;;
esac
