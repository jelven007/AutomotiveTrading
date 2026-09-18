# Ubuntu 单机部署指南

本文面向第一次部署服务器的使用者。完成后可通过浏览器访问 Quant Desk
页面。Docker Compose 会自动启动 Web、三个后端服务、MySQL、Redis、Kafka、
MinIO 和 Mailpit，并执行数据库迁移。

> 适用范围：开发、演示和集成验证环境。当前系统尚未接入完整交易链路，
> 不得用于真实资金交易。正式生产环境仍应按
> [部署与运维方案](deployment-and-operations.md)使用 VKE、托管数据库、
> KMS、HTTPS 和高可用架构。

## 1. 准备云服务器

推荐配置：

- 系统：Ubuntu Server 24.04 LTS，22.04 LTS 也可。
- 架构：x86_64。
- CPU：至少 4 核。
- 内存：至少 8 GB。
- 系统盘：至少 50 GB SSD。
- 公网 IP：1 个。

在云厂商安全组中添加入方向规则：

| 端口 | 来源 | 用途 |
| --- | --- | --- |
| `22/TCP` | 仅你的公网 IP | SSH 管理 |
| `80/TCP` | `0.0.0.0/0` | 当前 HTTP 页面 |
| `443/TCP` | 暂不开放 | 配置 HTTPS 后再开放 |

不要开放 `3306`、`6379`、`9092`、`8081`、`8001-8003`、`9000-9001`、`8025` 和 `1025`。部署文件已经将这些端口绑定到服务器回环地址，安全组仍应保持关闭。

## 2. 登录服务器

在本机终端执行，替换服务器 IP：

```bash
ssh ubuntu@你的服务器公网IP
```

如果云厂商提供的默认用户是 `root`，使用：

```bash
ssh root@你的服务器公网IP
```

## 3. 安装 Docker

以下命令在服务器上逐段执行：

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl git openssl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
```

添加 Docker 官方软件源：

```bash
architecture="$(dpkg --print-architecture)"
distribution="$(. /etc/os-release && echo "$VERSION_CODENAME")"
echo "deb [arch=${architecture} signed-by=/etc/apt/keyrings/docker.asc] \
https://download.docker.com/linux/ubuntu ${distribution} stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
```

安装并启动 Docker：

```bash
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io \
  docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"
```

退出 SSH 并重新登录，让 Docker 用户组生效：

```bash
exit
ssh ubuntu@你的服务器公网IP
```

验证安装：

```bash
docker version
docker compose version
docker run --rm hello-world
```

三条命令均成功后再继续。

## 4. 配置 GitHub SSH

在服务器生成 SSH 密钥：

```bash
ssh-keygen -t ed25519 -C "jelven@126.com"
cat ~/.ssh/id_ed25519.pub
```

一路按回车即可。复制 `cat` 输出的整行内容，然后：

1. 打开 GitHub。
2. 进入 `Settings` > `SSH and GPG keys`。
3. 点击 `New SSH key`。
4. 标题填写 `QuantTrading Ubuntu Server`。
5. 粘贴公钥并保存。

验证连接：

```bash
ssh -T git@github.com
```

第一次连接输入 `yes`。看到包含 GitHub 用户名的认证成功提示即可。

## 5. 下载项目

```bash
sudo mkdir -p /opt/quant-trading
sudo chown "$USER":"$USER" /opt/quant-trading
cd /opt/quant-trading
git clone git@github.com:jelven007/QuantTrading.git
cd QuantTrading
```

确认当前分支：

```bash
git status
```

应显示位于 `main` 分支，工作区没有修改。

## 6. 生成部署密钥

执行：

```bash
bash scripts/deploy.sh init
```

脚本会创建 `infra/compose/.env.deploy`，自动生成 MySQL、MinIO、JWT 和两个 Fernet 加密密钥，并将权限设置为仅当前用户可读写。

确认文件存在且权限为 `600`：

```bash
ls -l infra/compose/.env.deploy
```

不要把这个文件发送给他人，也不要提交到 Git。

## 7. 启动系统

执行：

```bash
bash scripts/deploy.sh up
```

第一次会下载基础镜像并构建业务镜像，通常需要 5 至 15 分钟。脚本会依次完成：

1. 校验 Compose 配置。
2. 构建 Web 和三个后端镜像。
3. 启动 MySQL 等基础服务。
4. 执行三个数据库的 Alembic 迁移。
5. 启动三个后端服务。
6. 启动 Nginx Web 入口。
7. 等待所有长期运行服务健康。

查看状态：

```bash
bash scripts/deploy.sh status
```

`web`、`identity-tenant`、`audit`、`model-config`、`mysql`、`redis`、
`kafka`、`minio` 和 `mailpit` 应显示为运行或健康。名称带 `-migrate`
和 `kafka-init` 的一次性容器正常完成后退出，不是故障。

## 8. 验证访问

在服务器执行：

```bash
curl http://127.0.0.1/health
curl -I http://127.0.0.1/settings/model-services
```

第一条应返回 `{"status":"ok"}`，第二条应返回 `HTTP/1.1 200 OK`。深层路径返回 200 表示 React Router 回退配置正常。

然后在本机浏览器打开：

```text
http://你的服务器公网IP
```

模型服务页面地址：

```text
http://你的服务器公网IP/settings/model-services
```

如果浏览器无法访问，依次检查：

```bash
bash scripts/deploy.sh status
curl http://127.0.0.1/health
sudo ss -lntp | grep ':80'
```

同时确认云安全组已放行 `80/TCP`。

## 9. 常用运维命令

查看全部日志：

```bash
bash scripts/deploy.sh logs
```

只查看 Web 或某个后端：

```bash
bash scripts/deploy.sh logs web
bash scripts/deploy.sh logs identity-tenant
bash scripts/deploy.sh logs model-config
```

按 `Ctrl+C` 退出日志，不会停止服务。

重启应用：

```bash
bash scripts/deploy.sh restart
```

停止全部服务并保留数据：

```bash
bash scripts/deploy.sh down
```

再次启动：

```bash
bash scripts/deploy.sh up
```

## 10. 更新版本

进入项目目录并拉取最新代码：

```bash
cd /opt/quant-trading/QuantTrading
git pull --ff-only origin main
bash scripts/deploy.sh up
```

`up` 会重新构建发生变化的镜像、执行数据库迁移并等待健康检查通过。

## 11. 备份 MySQL

创建备份目录并导出所有数据库：

```bash
cd /opt/quant-trading/QuantTrading
mkdir -p backups
docker compose \
  --env-file infra/compose/.env.deploy \
  -f infra/compose/docker-compose.yml \
  -f infra/compose/docker-compose.deploy.yml \
  exec -T mysql sh -c \
  'exec mysqldump -uroot -p"$MYSQL_ROOT_PASSWORD" \
    --all-databases --single-transaction' \
  > "backups/mysql-$(date +%Y%m%d-%H%M%S).sql"
```

检查备份文件不是空文件：

```bash
ls -lh backups/
```

还应将备份加密后复制到另一存储位置。只放在同一台服务器上不能应对磁盘损坏或服务器误删。

## 12. 重要安全说明

- 当前入口是 HTTP，只适合首次部署验证。对外正式使用前必须配置域名和 HTTPS。
- 推荐由云负载均衡或云 CDN 托管 TLS 证书，并将后端指向服务器 `80` 端口。
- 不要把 `.env.deploy`、数据库备份、API Key 或券商凭据提交到 Git。
- 不要直接删除 Docker 数据卷。`docker compose down -v` 会永久删除数据库数据。
- 修改已经初始化过的 MySQL 密码不会自动更新数据库内部账号，密码轮换必须按数据库运维流程执行。
- 真实资金交易上线前还必须完成完整交易域、风控、券商隔离、对账、灾备和安全验收。
