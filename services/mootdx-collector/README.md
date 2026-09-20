# Mootdx 采集 Sidecar

独立 Python 3.12 环境和锁文件，固定 mootdx 0.11.7 / tdxpy 0.2.7 / httpx 0.25.2。
主 workspace 排除本服务，核心 httpx 0.28 不受影响。

2026-09-20 确认的数据范围仅为上交所（SSE）和深交所（SZSE）A 股。
“全市场”指沪深；北交所不属于采集、补齐或验收范围。

## 启动与观察

已有本机基础组件时，使用 `bash scripts/deploy.sh market-up` 仅更新行情业务容器。
首次部署使用 `init`、`up`。已有部署配置缺少 ClickHouse 密码时，应先填回运行实例
使用的原密码，避免生成新密码后造成核心与数据库配置不一致。

本地运行使用真实环境变量，或 uv 的 `--env-file` 显式读取独立配置：

```bash
uv sync --project services/mootdx-collector --frozen
uv run --project services/mootdx-collector --env-file /安全位置/collector.env \
  python -m mootdx_collector once
uv run --project services/mootdx-collector --env-file /安全位置/collector.env \
  python -m mootdx_collector run
uv run --project services/mootdx-collector --env-file /安全位置/collector.env \
  python -m mootdx_collector status
```

`once` 采集一轮并等待至多 30 秒发送；发送失败仍保留队列，必须查看 pending 和
last_delivery_error，不能仅把进程退出码视为入库完成。`run` 恢复待发送数据并持续采集。
同一 spool 只允许一个采集进程；容器内可用 `docker compose exec mootdx-collector
python -m mootdx_collector status` 读取状态。不要同时启动共享卷的 `once` 和 `run`。

端口 8010 仅绑定宿主机回环地址。`/health/live` 仅返回存活状态，`/status` 需要
`X-Service-Token`，与核心的 `MARKET_INGEST_SERVICE_TOKEN` 相同。状态含候选证券数、
逐市场缺口、源日期、整轮耗时、待发送批次、累计接受条数以及节点哈希别名。
活着不等于行情可用，应联合检查最新轮次时间、覆盖与队列积压。

### 本机 macOS 常驻模式

本机 Colima 容器无法连接已经过宿主机实测可用的行情节点，因此使用独立 venv
和用户 LaunchAgent 持续采集。Docker 镜像已构建，采集容器暂时停止；核心和数据库
继续运行在 Docker。其他环境可直接使用上述 Compose 部署。

- 服务名：`net.quant-trading.mootdx-collector`。
- 配置：`~/Library/LaunchAgents/net.quant-trading.mootdx-collector.plist`。
- 数据、`collector.env`、`collector.log`：
  `~/Library/Application Support/quant-trading/mootdx-collector/`。
- 令牌只在权限为 `0600` 的 env 文件中；plist 通过 `uv run --env-file` 读取
  `~/.config/quant-trading/mootdx-collector.env` 符号链接，不包含令牌。
  使用无空格链接路径避免当前 uv 的 env-file 路径解析问题。
  服务使用当前主工作区的独立 venv，更新锁文件后需先执行 `uv sync`。
- 登录用户会话加载时启动，异常退出自动重启；退出登录或机器休眠期间不保证运行。
  默认只监听 `127.0.0.1:8010`。

```bash
launchctl print "gui/$(id -u)/net.quant-trading.mootdx-collector"
launchctl kickstart -k "gui/$(id -u)/net.quant-trading.mootdx-collector"
launchctl bootout "gui/$(id -u)/net.quant-trading.mootdx-collector"
launchctl bootstrap "gui/$(id -u)" \
  "$HOME/Library/LaunchAgents/net.quant-trading.mootdx-collector.plist"
curl http://127.0.0.1:8010/health/live
```

上述命令依次用于检查、重启、停止、恢复和存活探测，按需单独执行。
不要与 Compose Sidecar 同时占用 8010；两种模式的 SQLite 路径不同，
切换时须先处理原队列，不能将新实例空队列当作历史数据已送达。

## 数据契约与恢复

- 每批至多 80 只，同批同交易所，每个工作线程独占连接，默认 8 线程、最多 16。
- SQLite WAL + FULL 先保存压缩原始响应，再 HTTP 发送；成功后仍保留原始内容。
- 快照上报 `/internal/v1/market/quotes`，证券全集与覆盖报告上报 `/reports`，
  路径前缀均为 `/internal/v1/market`。批次 ID 重试不变。
- 核心保存原始行后逐行标准化，返回 received/accepted/rejected。确认条数或批次不匹配
  时不确认；401/4xx 退避 300 秒，其余错误指数退避至最多 60 秒。
- MySQL 保存核心确认凭证，相同 ID 不同内容返回 409；跨 MySQL/ClickHouse 失败时
  可重复物理写入原始行，event_id 按批次+行号确定，核验时按该字段逻辑去重。
- 队列超过 10,000 批、文件超过 10 GiB 或剩余磁盘不足 512 MiB 时停止下一轮采集。
  已在途响应仍保存，阈值是停止调度阈值；需为一轮原始响应预留空间。
- 本阶段无自动清理；定期备份整个 SQLite 数据库（使用 SQLite backup API），
  后续再接 MinIO 归档。不要运行中直接拷贝单个 `.sqlite3` 文件而遗漏 WAL。

## 覆盖与质量限制

沪深候选证券由 TDX 列表按 60/68、00/30 筛选，包括 302132 和 689009。
未配置 Tushare 时仅为候选集合，verification 为 unverified。配置 Token 后使用
`stock_basic(list_status=L)` 校准沪深全集；新基线要求先按 SSE/SZSE 过滤，
Token 不进日志或报告。

沪深采集通过显式市场编号（SZSE=0、SSE=1）取数，返回证券与市场均需属于请求集合。
按新基线，应采、实采、缺口和覆盖状态仅计算沪深；北交所不计入缺口，不触发降级。

上游时间只有时分秒；最新日 K 仅推定交易日，推定依据写入 metadata。
兼容层仅替换当前连接的快照命令：九点时间补齐小时前导零，异常短整数和越界时间
转换为未知值，`reversed_bytes0` 原始值继续保留，不影响同批其他证券返回。
缺失时间用明确哨兵；有效价格但未知时间标 unavailable，零价等无效行情标 invalid。
日期/单位未核验时不能 healthy；旧数据为 stale。
标准化用 Decimal 按证券精度处理浮点尾差、volunit 将成交量和盘口量换算为股。
原始层保留 tdxpy 返回值；不承诺网络解析从未使用 float。

标准快照表使用 ReplacingMergeTree，同证券同源时间的后续快照可能替换旧批次。
历史逐轮数量应核对原始层、覆盖报告和接收凭证，不能依赖标准表按旧 batch_id 计数。

2 秒为调度目标，整轮未结束不会叠加任务。周末、午间与夜间默认 300 秒；
尚未接入已核验节假日日历。交易时段 P95 ≤3 秒、五日稳定性需单独验收。
本阶段不接入策略信号，不改变实盘开关。

## 范围对齐状态

当前实现基于提交 `1f83870`，仍保留 BSE 枚举/不支持状态分支、
Tushare 名单映射和核心入参枚举；`Collector.once` 会将 BSE 的不完整状态
计入轮次聚合，因此沪深已全部返回时 `/status` 仍可能显示 `partial`。
这是旧范围的实现状态，不是当前需求中的北交所数据缺口。

本次仅同步文档。后续代码对齐应使 Provider/证券同步、Tushare 名单、行情契约、
采集调度及覆盖聚合统一限定 SSE/SZSE，并通过 `TC-CNMD-014` 验证。
对齐前按 `markets.SSE` 和 `markets.SZSE` 核对沪深覆盖，不将整体 `partial`
直接解释为沪深缺失；历史报告保留原值。源时间、质量和全集核验状态仍须独立检查。

## 离线验证

```bash
uv run --directory services/mootdx-collector pytest -v
uv run pytest services/instrument-market/tests tests/contract -v
uv run ruff check services/mootdx-collector services/instrument-market
```
