import { Plus, Search } from "lucide-react";
import { useMemo, useState } from "react";

// 状态到样式 tone 的映射，避免行内多层三元
const stateTone: Record<string, string> = {
  运行中: "success",
  已暂停: "warning",
  草稿: "neutral",
};

type Strategy = {
  name: string;
  version: string;
  state: string;
  pool: string;
  environment: string;
  pnl: string;
  updated: string;
};

// 策略数据：名称/版本、状态、标的池、环境、累计收益、最近运行
const strategies: Strategy[] = [
  {
    name: "多因子动量",
    version: "v12",
    state: "运行中",
    pool: "沪深 300",
    environment: "模拟",
    pnl: "+8.42%",
    updated: "刚刚",
  },
  {
    name: "港股价值轮动",
    version: "v7",
    state: "运行中",
    pool: "恒生综指",
    environment: "实盘",
    pnl: "+3.16%",
    updated: "12 秒前",
  },
  {
    name: "AI 财报事件",
    version: "v4",
    state: "已暂停",
    pool: "美股科技",
    environment: "模拟",
    pnl: "-0.74%",
    updated: "8 分钟前",
  },
  {
    name: "低波红利",
    version: "v9",
    state: "草稿",
    pool: "中证红利",
    environment: "未部署",
    pnl: "+5.08%",
    updated: "昨天",
  },
];

// 策略列表行：复用全站数据表样式（.table-scroll），保证与交易页表格风格一致
function StrategyRow({ strategy }: { strategy: Strategy }) {
  const positive = strategy.pnl.startsWith("+");
  return (
    <tr>
      <td>
        <strong>{strategy.name}</strong>
        <small className="row-subtext">{strategy.version}</small>
      </td>
      <td>
        <span className={`state state--${stateTone[strategy.state]}`}>
          {strategy.state}
        </span>
      </td>
      <td>{strategy.pool}</td>
      <td>{strategy.environment}</td>
      <td className={positive ? "metric-positive" : "metric-negative"}>
        {strategy.pnl}
      </td>
      <td className="row-muted">{strategy.updated}</td>
    </tr>
  );
}

export function StrategiesPage() {
  const [keyword, setKeyword] = useState("");

  // 按名称模糊过滤，忽略大小写与首尾空白
  const filtered = useMemo(() => {
    const term = keyword.trim().toLowerCase();
    if (!term) {
      return strategies;
    }
    return strategies.filter((item) => item.name.toLowerCase().includes(term));
  }, [keyword]);

  return (
    <div className="page">
      <section aria-labelledby="strategy-list">
        <div className="section-heading section-heading--tools">
          <div>
            <h2 id="strategy-list">策略</h2>
            <span>按最近运行排序</span>
          </div>
          <div className="tools-row">
            <label className="search-field search-field--compact">
              <Search size={16} />
              <input
                aria-label="搜索策略"
                placeholder="搜索策略"
                value={keyword}
                onChange={(event) => setKeyword(event.target.value)}
              />
            </label>
            <button className="button button--primary" type="button">
              <Plus size={16} />
              策略
            </button>
          </div>
        </div>
        {filtered.length === 0 ? (
          <div className="binance-section-state">没有匹配的策略</div>
        ) : (
          <div className="table-scroll list-panel">
            <table>
              <thead>
                <tr>
                  <th>策略</th>
                  <th>状态</th>
                  <th>标的池</th>
                  <th>环境</th>
                  <th>累计收益</th>
                  <th>最近运行</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((strategy) => (
                  <StrategyRow key={strategy.name} strategy={strategy} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
