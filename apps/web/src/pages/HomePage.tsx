import {
  AlertTriangle,
  ArrowDownRight,
  ArrowUpRight,
  CheckCircle2,
  FlaskConical,
  PauseCircle,
  Play,
  Plus,
} from "lucide-react";

const markets = [
  {
    name: "上证指数",
    code: "000001.SH",
    value: "3,382.41",
    change: "+0.42%",
    status: "交易中",
    time: "10:31 CST",
    trend: "up",
    points: "0,35 25,28 50,31 75,18 100,22 125,9 150,12",
  },
  {
    name: "恒生指数",
    code: "HSI.HK",
    value: "24,912.16",
    change: "-0.18%",
    status: "交易中",
    time: "10:31 HKT",
    trend: "down",
    points: "0,12 25,17 50,14 75,24 100,20 125,31 150,29",
  },
  {
    name: "纳斯达克",
    code: "IXIC.US",
    value: "22,261.33",
    change: "+0.81%",
    status: "已收盘",
    time: "16:00 EDT",
    trend: "up",
    points: "0,34 25,29 50,31 75,19 100,21 125,11 150,7",
  },
];

const strategies = [
  {
    name: "多因子动量",
    scope: "沪深 300 · v12",
    state: "运行中",
    tone: "success",
    pnl: "+8.42%",
    updated: "刚刚",
  },
  {
    name: "港股价值轮动",
    scope: "恒生综指 · v7",
    state: "运行中",
    tone: "success",
    pnl: "+3.16%",
    updated: "12 秒前",
  },
  {
    name: "AI 财报事件",
    scope: "美股科技 · v4",
    state: "已暂停",
    tone: "warning",
    pnl: "-0.74%",
    updated: "8 分钟前",
  },
];

function MiniChart({ points, trend }: { points: string; trend: string }) {
  return (
    <svg
      className={`mini-chart mini-chart--${trend}`}
      viewBox="0 0 150 42"
      aria-hidden="true"
    >
      <polyline
        points={points}
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
      />
    </svg>
  );
}

export function HomePage() {
  return (
    <div className="page">
      <div className="page-heading">
        <div>
          <p className="eyebrow">2026 年 9 月 18 日 · 星期五</p>
          <h1>交易控制台</h1>
          <p className="page-description">
            聚合市场、策略与账户状态，处理需要人工介入的事项。
          </p>
        </div>
        <div className="page-actions">
          <button className="button button--secondary">
            <FlaskConical size={16} />
            新建回测
          </button>
          <button className="button button--primary">
            <Plus size={16} />
            创建策略
          </button>
        </div>
      </div>

      <section aria-labelledby="market-overview">
        <div className="section-heading">
          <div>
            <h2 id="market-overview">市场概览</h2>
            <span>行情源 QMT / Futu · 128ms</span>
          </div>
          <button className="text-button">查看全部行情</button>
        </div>
        <div className="market-grid">
          {markets.map((market) => (
            <article className="market-tile" key={market.code}>
              <div className="tile-topline">
                <div>
                  <strong>{market.name}</strong>
                  <small>{market.code}</small>
                </div>
                <span
                  className={`market-status market-status--${market.status === "交易中" ? "open" : "closed"}`}
                >
                  {market.status}
                </span>
              </div>
              <div className="market-value-row">
                <div>
                  <span className="market-value">{market.value}</span>
                  <span className={`change change--${market.trend}`}>
                    {market.trend === "up" ? (
                      <ArrowUpRight size={14} />
                    ) : (
                      <ArrowDownRight size={14} />
                    )}
                    {market.change}
                  </span>
                </div>
                <MiniChart points={market.points} trend={market.trend} />
              </div>
              <small className="market-time">{market.time}</small>
            </article>
          ))}
        </div>
      </section>

      <div className="dashboard-grid">
        <section className="panel asset-panel" aria-labelledby="asset-overview">
          <div className="panel-heading">
            <div>
              <h2 id="asset-overview">资产概览</h2>
              <span>按交易环境隔离</span>
            </div>
            <button className="text-button">资产明细</button>
          </div>
          <div className="asset-columns">
            <div className="asset-block">
              <span className="environment-label environment-label--simulation">
                模拟交易
              </span>
              <strong className="asset-total">¥ 1,284,620.40</strong>
              <span className="metric-positive">今日 +¥ 6,248.20 · +0.49%</span>
              <dl className="asset-details">
                <div>
                  <dt>可用资金</dt>
                  <dd>¥ 482,100</dd>
                </div>
                <div>
                  <dt>持仓市值</dt>
                  <dd>¥ 802,520</dd>
                </div>
              </dl>
            </div>
            <div className="asset-block">
              <span className="environment-label environment-label--live">
                实盘交易
              </span>
              <strong className="asset-total">HK$ 864,912.70</strong>
              <span className="metric-negative">
                今日 -HK$ 1,842.60 · -0.21%
              </span>
              <dl className="asset-details">
                <div>
                  <dt>可用资金</dt>
                  <dd>HK$ 328,700</dd>
                </div>
                <div>
                  <dt>持仓市值</dt>
                  <dd>HK$ 536,213</dd>
                </div>
              </dl>
            </div>
          </div>
        </section>

        <section className="panel attention-panel" aria-labelledby="attention">
          <div className="panel-heading">
            <div>
              <h2 id="attention">待处理</h2>
              <span>2 项需要确认</span>
            </div>
            <span className="count-badge">2</span>
          </div>
          <div className="attention-list">
            <button className="attention-item">
              <span className="attention-icon attention-icon--warning">
                <AlertTriangle size={17} />
              </span>
              <span>
                <strong>实盘信号待确认</strong>
                <small>腾讯控股 · 买入 300 股</small>
              </span>
              <time>2 分钟</time>
            </button>
            <button className="attention-item">
              <span className="attention-icon attention-icon--danger">
                <PauseCircle size={17} />
              </span>
              <span>
                <strong>策略因数据延迟暂停</strong>
                <small>AI 财报事件 · NASDAQ</small>
              </span>
              <time>8 分钟</time>
            </button>
            <div className="attention-item attention-item--resolved">
              <span className="attention-icon attention-icon--success">
                <CheckCircle2 size={17} />
              </span>
              <span>
                <strong>券商对账完成</strong>
                <small>Futu OpenD · 无差异</small>
              </span>
              <time>10:15</time>
            </div>
          </div>
        </section>

        <section
          className="panel strategy-panel"
          aria-labelledby="strategy-status"
        >
          <div className="panel-heading">
            <div>
              <h2 id="strategy-status">策略运行</h2>
              <span>2 运行 · 1 暂停</span>
            </div>
            <button className="text-button">管理策略</button>
          </div>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>策略</th>
                  <th>状态</th>
                  <th>累计收益</th>
                  <th>最近运行</th>
                  <th aria-label="操作" />
                </tr>
              </thead>
              <tbody>
                {strategies.map((strategy) => (
                  <tr key={strategy.name}>
                    <td>
                      <strong>{strategy.name}</strong>
                      <small>{strategy.scope}</small>
                    </td>
                    <td>
                      <span className={`state state--${strategy.tone}`}>
                        {strategy.state}
                      </span>
                    </td>
                    <td
                      className={
                        strategy.pnl.startsWith("+")
                          ? "metric-positive"
                          : "metric-negative"
                      }
                    >
                      {strategy.pnl}
                    </td>
                    <td>{strategy.updated}</td>
                    <td>
                      <button
                        className="icon-button icon-button--small"
                        aria-label={`运行 ${strategy.name}`}
                        title="运行"
                      >
                        <Play size={15} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section className="panel watchlist-panel" aria-labelledby="watchlist">
          <div className="panel-heading">
            <div>
              <h2 id="watchlist">自选行情</h2>
              <span>核心观察池</span>
            </div>
            <button
              className="icon-button icon-button--small"
              aria-label="添加自选股"
              title="添加自选股"
            >
              <Plus size={15} />
            </button>
          </div>
          <div className="quote-list">
            {[
              ["贵州茅台", "600519.SH", "1,456.20", "+1.24%"],
              ["腾讯控股", "00700.HK", "612.50", "-0.32%"],
              ["NVIDIA", "NVDA.US", "178.43", "+2.08%"],
            ].map(([name, code, price, change]) => (
              <div className="quote-row" key={code}>
                <span>
                  <strong>{name}</strong>
                  <small>{code}</small>
                </span>
                <span>
                  <strong>{price}</strong>
                  <small
                    className={
                      change.startsWith("+")
                        ? "metric-positive"
                        : "metric-negative"
                    }
                  >
                    {change}
                  </small>
                </span>
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
