# Binance NautilusTrader M0 POC 验收记录

> 文档编号：QT-RESULT-BIN-NT-M0-001
>
> 日期：2026-09-20
>
> 结果：通过

## 1. 范围

本轮只验证 NautilusTrader 能否作为币安现货与 U 本位运行时依赖，并建立后续
Runtime Manager 可复用的配置构造器。不连接 Binance，不加载真实凭据，不下单。

## 2. 依赖验证

| 项目 | 结果 |
| --- | --- |
| Python | 3.12 |
| NautilusTrader | 1.231.0，精确锁定 |
| 本机构架 | macOS arm64 wheel 可安装 |
| ECS 架构 | Linux x86_64 |
| ECS wheel | 存在 `cp312-manylinux_2_35_x86_64` |

实际安装包公共 API 与最新在线示例存在命名差异。本版本使用：

- `BinanceAccountType.SPOT`
- `BinanceAccountType.USDT_FUTURES`
- `BinanceDataClientConfig`
- `BinanceExecClientConfig`
- `BinanceEnvironment.LIVE|TESTNET`

未使用在线示例中的 `BinanceProductType` 或
`BinanceExecutionClientConfig`。

## 3. 实现

新增：

```text
services/trading/src/trading/binance_runtime/__init__.py
services/trading/src/trading/binance_runtime/config.py
services/trading/tests/test_nautilus_config.py
```

`build_binance_client_configs`：

- 构造 `BINANCE_SPOT` 与 `BINANCE_FUTURES` 两组配置。
- 分别使用 Spot 与 USDT Futures 帐号类型。
- 明确映射 LIVE 和 TESTNET。
- 无凭据时仅生成数据客户端。
- 凭据必须成对提供。
- 只接受 HMAC 和 Ed25519。

## 4. 自动化结果

```text
uv run pytest services/trading/tests/test_nautilus_config.py -v
7 passed

uv run pytest services/trading/tests -q
101 passed, 2 warnings

uv run ruff format --check ...
3 files already formatted

uv run ruff check ...
All checks passed

uv run mypy services/trading/src/trading/binance_runtime
Success: no issues found in 2 source files
```

两个 warning 来自 FastAPI/Starlette 测试客户端依赖弃用，与本次 POC 无关。

## 5. 未覆盖

- 未创建或启动 Nautilus `LiveNode`。
- 未连接 Binance Testnet 或生产环境。
- 未加载 instrument。
- 未验证订单、成交、余额、持仓、杠杆和保证金模式。
- 未验证 Docker 镜像安装时间和运行内存。

以上属于后续 M1-M3，不计为 M0 失败。
