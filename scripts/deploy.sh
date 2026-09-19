#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${QT_DEPLOY_ENV_FILE:-${ROOT_DIR}/infra/compose/.env.deploy}"
COMPOSE_FILES=(
  -f "${ROOT_DIR}/infra/compose/docker-compose.yml"
  -f "${ROOT_DIR}/infra/compose/docker-compose.deploy.yml"
)

usage() {
  cat <<'EOF'
用法：bash scripts/deploy.sh <命令>

命令：
  init      生成部署环境文件和强随机密钥
  up        构建镜像、执行迁移并启动全部服务
  readonly-up  启动默认服务及币安只读 UAT Profile
  status    查看容器状态
  logs      查看日志，可追加服务名
  restart   重启 Web 和默认后端服务
  down      停止服务但保留数据库数据
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
    echo "部署配置已存在，未覆盖：${ENV_FILE}"
    return
  fi

  mkdir -p "$(dirname "${ENV_FILE}")"
  umask 077
  cat >"${ENV_FILE}" <<EOF
# 由 scripts/deploy.sh init 自动生成，请勿提交到 Git。
MYSQL_ROOT_PASSWORD=$(openssl rand -hex 24)
MYSQL_DATABASE=qt_platform
MYSQL_USER=qt_app
MYSQL_PASSWORD=$(openssl rand -hex 24)
MINIO_ROOT_USER=qt_minio
MINIO_ROOT_PASSWORD=$(openssl rand -hex 24)

QT_BIND_HOST=127.0.0.1
QT_MYSQL_PORT=3306
QT_REDIS_PORT=6379
QT_KAFKA_PORT=9092
QT_SCHEMA_REGISTRY_PORT=8081
QT_MINIO_PORT=9000
QT_MINIO_CONSOLE_PORT=9001
QT_MAILPIT_SMTP_PORT=1025
QT_MAILPIT_PORT=8025

AUTH_JWT_SECRET=$(openssl rand -hex 48)
AUTH_TOTP_ENCRYPTION_KEY=$(fernet_key)
SECRET_ENCRYPTION_KEY=$(fernet_key)
KMS_SERVICE_TOKEN=$(openssl rand -hex 48)
RISK_SERVICE_TOKEN=$(openssl rand -hex 48)

KMS_KEY_ID=
KMS_REGION=cn-beijing
VOLCENGINE_ACCESS_KEY=
VOLCENGINE_SECRET_KEY=
VOLCENGINE_SESSION_TOKEN=
FIXED_EGRESS_IP_CONFIGURED=false
PUBLIC_BASE_URL=

ENVIRONMENT=production
WEB_PORT=80
IDENTITY_PORT=8001
AUDIT_PORT=8002
MODEL_CONFIG_PORT=8003
TRADING_PORT=8004
RISK_PORT=8005
KMS_ADAPTER_PORT=8006
EOF
  chmod 600 "${ENV_FILE}"
  echo "已生成部署配置：${ENV_FILE}"
}

require_deployment() {
  if [[ ! -f "${ENV_FILE}" ]]; then
    echo "部署配置不存在，请先执行：bash scripts/deploy.sh init" >&2
    exit 1
  fi
  if grep -q "please-change" "${ENV_FILE}"; then
    echo "部署配置仍包含 please-change 占位值，请删除后重新执行 init。" >&2
    exit 1
  fi
  require_command docker
  docker compose version >/dev/null
}

env_value() {
  sed -n "s/^$1=//p" "${ENV_FILE}" | tail -n 1
}

require_readonly_configuration() {
  local name value
  if [[ ! -f "${ENV_FILE}" ]]; then
    echo "部署配置不存在，请先执行：bash scripts/deploy.sh init" >&2
    return 1
  fi
  for name in \
    KMS_KEY_ID \
    VOLCENGINE_ACCESS_KEY \
    VOLCENGINE_SECRET_KEY \
    KMS_SERVICE_TOKEN \
    RISK_SERVICE_TOKEN; do
    value="$(env_value "${name}")"
    if [[ -z "${value}" || "${value}" == please-change* ]]; then
      echo "币安只读 UAT 需要配置 ${name}。" >&2
      return 1
    fi
  done
  for name in KMS_SERVICE_TOKEN RISK_SERVICE_TOKEN; do
    value="$(env_value "${name}")"
    if ((${#value} < 32)); then
      echo "${name} 必须至少包含 32 个字符。" >&2
      return 1
    fi
  done
  if [[ "$(env_value KMS_SERVICE_TOKEN)" == "$(env_value RISK_SERVICE_TOKEN)" ]]; then
    echo "KMS_SERVICE_TOKEN 与 RISK_SERVICE_TOKEN 必须不同。" >&2
    return 1
  fi
  if [[ "$(env_value FIXED_EGRESS_IP_CONFIGURED)" != "true" ]]; then
    echo "完成币安 IP 白名单后，将 FIXED_EGRESS_IP_CONFIGURED 设置为 true。" >&2
    return 1
  fi
  if [[ "$(env_value PUBLIC_BASE_URL)" != https://* ]]; then
    echo "币安只读 UAT 需要配置 HTTPS 格式的 PUBLIC_BASE_URL。" >&2
    return 1
  fi
}

readonly_profile_enabled() {
  [[ ",${COMPOSE_PROFILES:-}," == *",binance-readonly,"* ]]
}

compose_cmd() {
  docker compose \
    --env-file "${ENV_FILE}" \
    "${COMPOSE_FILES[@]}" \
    "$@"
}

wait_for_jobs() {
  local jobs=(
    kafka-init identity-migrate audit-migrate model-config-migrate
  )
  if readonly_profile_enabled; then
    jobs+=(
      readonly-databases-init kms-adapter-migrate risk-migrate trading-migrate
    )
  fi
  local deadline=$((SECONDS + ${QT_DEPLOY_WAIT_SECONDS:-300}))
  local container_id exit_code job pending state

  while ((SECONDS < deadline)); do
    pending=""
    for job in "${jobs[@]}"; do
      container_id="$(compose_cmd ps -a -q "${job}")"
      if [[ -z "${container_id}" ]]; then
        pending="${pending} ${job}(未启动)"
        continue
      fi

      state="$(docker inspect --format '{{.State.Status}}' "${container_id}")"
      if [[ "${state}" == "exited" ]]; then
        exit_code="$(docker inspect --format '{{.State.ExitCode}}' "${container_id}")"
        if [[ "${exit_code}" == "0" ]]; then
          continue
        fi
        echo "一次性任务失败：${job}（exit=${exit_code}）" >&2
        compose_cmd logs --tail=100 "${job}" >&2
        return 1
      fi
      if [[ "${state}" == "dead" ]]; then
        echo "一次性任务异常终止：${job}" >&2
        compose_cmd logs --tail=100 "${job}" >&2
        return 1
      fi
      pending="${pending} ${job}(${state})"
    done

    if [[ -z "${pending}" ]]; then
      return
    fi
    echo "等待初始化任务：${pending# }"
    sleep 2
  done

  echo "等待初始化任务超时。" >&2
  compose_cmd ps -a >&2
  return 1
}

wait_for_services() {
  local services=(
    mysql redis kafka minio mailpit
    identity-tenant audit model-config web
  )
  if readonly_profile_enabled; then
    services+=(kms-adapter risk trading)
  fi
  local deadline=$((SECONDS + ${QT_DEPLOY_WAIT_SECONDS:-300}))
  local container_id health pending service state

  while ((SECONDS < deadline)); do
    pending=""
    for service in "${services[@]}"; do
      container_id="$(compose_cmd ps -a -q "${service}")"
      if [[ -z "${container_id}" ]]; then
        pending="${pending} ${service}(未启动)"
        continue
      fi

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
  compose_cmd ps >&2
  return 1
}

command="${1:-help}"
case "${command}" in
  init)
    init_env
    ;;
  up)
    require_deployment
    compose_cmd config --quiet
    compose_cmd up -d --build --remove-orphans
    wait_for_jobs
    wait_for_services
    web_port="${WEB_PORT:-$(sed -n 's/^WEB_PORT=//p' "${ENV_FILE}" | tail -n 1)}"
    echo "部署完成：http://<服务器公网 IP>:${web_port:-80}"
    compose_cmd ps -a
    ;;
  readonly-up)
    require_readonly_configuration
    require_deployment
    export COMPOSE_PROFILES=binance-readonly
    compose_cmd config --quiet
    compose_cmd up -d --build --remove-orphans
    wait_for_jobs
    wait_for_services
    echo "币安只读 UAT 部署完成：$(env_value PUBLIC_BASE_URL)"
    compose_cmd ps -a
    ;;
  status)
    require_deployment
    compose_cmd ps -a
    ;;
  logs)
    require_deployment
    shift
    compose_cmd logs --tail=200 -f "$@"
    ;;
  restart)
    require_deployment
    compose_cmd restart identity-tenant audit model-config web
    compose_cmd ps -a
    ;;
  down)
    require_deployment
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
