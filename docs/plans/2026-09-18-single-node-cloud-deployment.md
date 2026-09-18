# Ubuntu 单机云部署实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use
> superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为当前 M2 系统提供可在 Ubuntu 云服务器上一键启动的 Docker Compose 部署入口。

**Architecture:** 复用现有基础设施 Compose，通过部署覆盖文件增加数据库迁移、
三个 FastAPI 服务和 Web 入口。Web 使用 Node 22 多阶段构建，并由非特权
Nginx 提供静态资源、SPA 路由回退和同源 API 反向代理；除 Web 外的宿主机
端口仅绑定到回环地址。

**Tech Stack:** Docker Compose、Node.js 22、pnpm 10、Vite、Nginx、
FastAPI、Alembic、MySQL 8.4。

---

## Task 1: 部署文件验收测试

**Files:**

- Create: `scripts/tests/test_deployment_files.py`

**Steps:**

1. 编写失败测试，检查 Web 镜像、Nginx SPA/API 配置、Compose 服务和部署脚本。
2. 运行 `uv run pytest scripts/tests/test_deployment_files.py -v`，确认因文件缺失而失败。

## Task 2: Web 镜像与入口代理

**Files:**

- Create: `apps/web/Dockerfile`
- Create: `apps/web/nginx.conf`
- Create: `.dockerignore`
- Modify: `infra/compose/docker-compose.yml`
- Modify: `infra/compose/docker-compose.deploy.yml`

**Steps:**

1. 使用仓库根目录作为构建上下文，仅安装 Web workspace 依赖并生成 Vite 产物。
2. 使用非特权 Nginx 在容器 `8080` 端口提供 Web 页面。
3. 配置 `/api/v1/auth/`、`/api/v1/tenants/` 和模型配置接口代理。
4. 配置 `try_files $uri $uri/ /index.html` 支持 React Router 刷新。
5. 将 Web 作为唯一公网入口，其他端口通过 `QT_BIND_HOST` 绑定回环地址。
6. 运行部署文件测试，确认通过。

## Task 3: 一键部署与新手文档

**Files:**

- Create: `scripts/deploy.sh`
- Create: `docs/operations/ubuntu-single-node-deployment.md`
- Modify: `infra/compose/.env.deploy.example`
- Modify: `README.md`

**Steps:**

1. 实现 `init`、`up`、`status`、`logs`、`restart`、`down` 命令。
2. `init` 自动生成 MySQL、MinIO、JWT 和 Fernet 密钥，并将环境文件权限设为 `600`。
3. 文档提供 Ubuntu 安装 Docker、拉取仓库、开放端口、部署、升级、备份和故障排查步骤。
4. 运行部署文件测试和 Shell 语法检查。

## Task 4: 端到端部署验证

**Files:**

- Verify: `infra/compose/docker-compose.yml`
- Verify: `infra/compose/docker-compose.deploy.yml`

**Steps:**

1. 使用临时项目名和临时端口构建全部镜像。
2. 启动依赖、执行 Alembic 迁移并等待服务健康。
3. 验证 Web `/health`、首页、SPA 深层路由、身份接口和模型配置代理。
4. 清理临时容器、网络和数据卷。

## Task 5: 全量检查与交付

**Steps:**

1. 运行 `make lint`、`make test` 和 `make build`。
2. 检查 Git 差异，确认未提交真实密钥或运行时数据。
3. 提交部署文件并推送 `origin/main`。
