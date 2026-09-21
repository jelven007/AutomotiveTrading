import { MoreHorizontal, Plus, Search } from "lucide-react";

// 顶部四张统计卡
const stats = [
  { label: "策略总数", value: "12" },
  { label: "运行中", value: "6" },
  { label: "本月模型调用", value: "18,420" },
  { label: "预算使用", value: "42%" },
];

// 状态到样式 tone 的映射，避免行内多层三元
const stateTone: Record<string, string> = {
  运行中: "success",
  已暂停: "warning",
  草稿: "neutral",
};

// 全部策略表格数据：名称/版本、状态、标的池、环境、累计收益、最近运行
const rows = [
  ["多因子动量", "v12", "运行中", "沪深 300", "模拟", "+8.42%", "刚刚"],
  ["港股价值轮动", "v7", "运行中", "恒生综指", "实盘", "+3.16%", "12 秒前"],
  ["AI 财报事件", "v4", "已暂停", "美股科技", "模拟", "-0.74%", "8 分钟前"],
  ["低波红利", "v9", "草稿", "中证红利", "未部署", "+5.08%", "昨天"],
];

export function StrategiesPage() {
  return (
    <div className="page">
      <div className="page-heading">
        <div>
          <p className="eyebrow">研究与执行</p>
          <h1>策略</h1>
          <p className="page-description">
            管理版本、标的池、回测结果与交易部署。
          </p>
        </div>
        <button className="button button--primary" type="button">
          <Plus size={16} />
          创建策略
        </button>
      </div>

      <div className="summary-strip">
        {stats.map((stat) => (
          <div key={stat.label}>
            <span>{stat.label}</span>
            <strong>{stat.value}</strong>
          </div>
        ))}
      </div>

      <section className="panel list-panel" aria-labelledby="strategy-list">
        <div className="panel-heading panel-heading--tools">
          <div>
            <h2 id="strategy-list">全部策略</h2>
            <span>按最近运行排序</span>
          </div>
          <label className="search-field search-field--compact">
            <Search size={16} />
            <input aria-label="搜索策略" placeholder="搜索策略" />
          </label>
        </div>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>名称 / 版本</th>
                <th>状态</th>
                <th>标的池</th>
                <th>环境</th>
                <th>累计收益</th>
                <th>最近运行</th>
                <th aria-label="操作" />
              </tr>
            </thead>
            <tbody>
              {rows.map(
                ([name, version, state, pool, environment, pnl, updated]) => (
                  <tr key={name}>
                    <td>
                      <strong>{name}</strong>
                      <small>{version}</small>
                    </td>
                    <td>
                      <span className={`state state--${stateTone[state]}`}>
                        {state}
                      </span>
                    </td>
                    <td>{pool}</td>
                    <td>{environment}</td>
                    <td
                      className={
                        pnl.startsWith("+")
                          ? "metric-positive"
                          : "metric-negative"
                      }
                    >
                      {pnl}
                    </td>
                    <td>{updated}</td>
                    <td>
                      <button
                        className="icon-button icon-button--small"
                        aria-label={`${name} 更多操作`}
                        title="更多操作"
                        type="button"
                      >
                        <MoreHorizontal size={16} />
                      </button>
                    </td>
                  </tr>
                ),
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
