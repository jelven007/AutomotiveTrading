import {
  AlertOctagon,
  ArrowRight,
  CircleDollarSign,
  RefreshCw,
  ShieldCheck,
} from "lucide-react";

const orders = [
  ["10:28:42", "贵州茅台", "买入", "100", "1,456.20", "全部成交"],
  ["10:16:08", "腾讯控股", "卖出", "300", "612.50", "部分成交"],
  ["09:48:21", "宁德时代", "买入", "500", "342.18", "已提交"],
];

export function TradingPage() {
  return (
    <div className="page">
      <div className="page-heading">
        <div>
          <p className="eyebrow">订单与账户</p>
          <h1>交易</h1>
          <p className="page-description">
            交易环境严格隔离；实盘自动交易默认关闭。
          </p>
        </div>
        <div className="page-actions">
          <button className="button button--secondary">
            <RefreshCw size={16} />
            对账
          </button>
          <button className="button button--danger">
            <AlertOctagon size={16} />
            急停
          </button>
        </div>
      </div>

      <div className="environment-grid">
        <section
          className="environment-card environment-card--simulation"
          aria-labelledby="simulation-title"
        >
          <div className="environment-card__header">
            <div>
              <span className="environment-kicker">SIMULATION</span>
              <h2 id="simulation-title">模拟交易</h2>
            </div>
            <span className="connection-state connection-state--ok">
              已连接
            </span>
          </div>
          <dl className="environment-meta">
            <div>
              <dt>账户</dt>
              <dd>SIM-A-8302</dd>
            </div>
            <div>
              <dt>撮合引擎</dt>
              <dd>平台模拟撮合</dd>
            </div>
            <div>
              <dt>市场</dt>
              <dd>A 股 · 交易中</dd>
            </div>
          </dl>
          <div className="environment-balance">
            <span>总资产 CNY</span>
            <strong>¥ 1,284,620.40</strong>
            <small className="metric-positive">今日 +0.49%</small>
          </div>
          <button className="button button--primary button--full">
            模拟下单
            <ArrowRight size={16} />
          </button>
        </section>

        <section
          className="environment-card environment-card--live"
          aria-labelledby="live-title"
        >
          <div className="environment-card__header">
            <div>
              <span className="environment-kicker">LIVE</span>
              <h2 id="live-title">实盘交易</h2>
            </div>
            <span className="connection-state connection-state--ok">
              Futu 已连接
            </span>
          </div>
          <dl className="environment-meta">
            <div>
              <dt>账户</dt>
              <dd>FUTU-HK-0218</dd>
            </div>
            <div>
              <dt>券商通道</dt>
              <dd>Futu OpenD</dd>
            </div>
            <div>
              <dt>市场</dt>
              <dd>港股 · 交易中</dd>
            </div>
          </dl>
          <div className="environment-balance">
            <span>总资产 HKD</span>
            <strong>HK$ 864,912.70</strong>
            <small className="metric-negative">今日 -0.21%</small>
          </div>
          <div className="live-guard">
            <ShieldCheck size={16} />
            自动实盘关闭 · 人工确认开启
          </div>
        </section>
      </div>

      <div className="trading-summary">
        <div>
          <CircleDollarSign size={18} />
          <span>今日成交额</span>
          <strong>¥ 286,420</strong>
        </div>
        <div>
          <span>待确认信号</span>
          <strong>2</strong>
        </div>
        <div>
          <span>风控拒绝</span>
          <strong>1</strong>
        </div>
        <div>
          <span>状态未知订单</span>
          <strong>0</strong>
        </div>
      </div>

      <section className="panel list-panel" aria-labelledby="recent-orders">
        <div className="panel-heading">
          <div>
            <h2 id="recent-orders">最近订单</h2>
            <span>统一订单状态视图</span>
          </div>
          <button className="text-button">全部订单</button>
        </div>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>时间</th>
                <th>标的</th>
                <th>方向</th>
                <th>数量</th>
                <th>价格</th>
                <th>状态</th>
              </tr>
            </thead>
            <tbody>
              {orders.map((order) => (
                <tr key={`${order[0]}-${order[1]}`}>
                  {order.map((value, index) => (
                    <td
                      key={value}
                      className={
                        index === 2
                          ? value === "买入"
                            ? "metric-positive"
                            : "metric-negative"
                          : ""
                      }
                    >
                      {value}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
