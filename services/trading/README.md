# Trading

B Demo 单账号服务，提供：

- HMAC API Key 安全替换与删除。
- Demo 账号签名校验。
- NautilusTrader Spot 与 USD-M 双客户端。
- 现货余额、U 本位余额和非零持仓聚合查询。
- AES-256-GCM 本地凭据加密。

当前接口：

```text
GET    /api/v1/trading/binance/account
PUT    /api/v1/trading/binance/account
DELETE /api/v1/trading/binance/account
GET    /api/v1/trading/binance/overview
```

本地启动：

```bash
cp .env.example .env
uv run uvicorn trading.main:app --reload
```

部署环境必须挂载 32 字节主密钥，并保持：

```text
BINANCE_ENVIRONMENT=demo
DEMO_TRADING_ENABLED=false
```

当前版本不会构造主网客户端；Demo 下单接口完成前，模拟交易写入也保持关闭。
