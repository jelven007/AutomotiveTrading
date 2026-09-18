import { DatabaseZap, Search, SlidersHorizontal } from "lucide-react";

const datasets = [
  ["证券主数据", "三市场证券与代码映射", "T+0", "09:30:02", "正常"],
  ["分钟 K 线", "1m OHLCV 前复权", "1 分钟", "10:31:00", "正常"],
  ["财务指标", "标准化财报与派生指标", "每日", "07:12:44", "正常"],
  ["新闻事件", "新闻、公告、研报与财报事件", "实时", "10:30:52", "延迟"],
];

export function DataPage() {
  return (
    <div className="page">
      <div className="page-heading">
        <div>
          <p className="eyebrow">数据目录</p>
          <h1>数据</h1>
          <p className="page-description">
            查看数据定义、来源、新鲜度与跨供应商映射。
          </p>
        </div>
        <button className="button button--primary">
          <DatabaseZap size={16} />
          数据查询
        </button>
      </div>

      <div className="provider-strip">
        <div>
          <span className="status-dot status-dot--ok" />
          <span>Mock Market</span>
          <strong>128ms</strong>
        </div>
        <div>
          <span className="status-dot status-dot--ok" />
          <span>Futu Quote</span>
          <strong>214ms</strong>
        </div>
        <div>
          <span className="status-dot status-dot--warning" />
          <span>News Feed</span>
          <strong>8s</strong>
        </div>
      </div>

      <section className="panel list-panel" aria-labelledby="data-catalog">
        <div className="panel-heading panel-heading--tools">
          <div>
            <h2 id="data-catalog">数据集</h2>
            <span>生产 Schema · Mock Provider 可用</span>
          </div>
          <div className="inline-tools">
            <label className="search-field search-field--compact">
              <Search size={16} />
              <input aria-label="搜索数据集" placeholder="搜索数据集" />
            </label>
            <button
              className="icon-button"
              aria-label="筛选数据集"
              title="筛选"
            >
              <SlidersHorizontal size={17} />
            </button>
          </div>
        </div>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>数据集</th>
                <th>说明</th>
                <th>频率</th>
                <th>最新数据</th>
                <th>状态</th>
              </tr>
            </thead>
            <tbody>
              {datasets.map(
                ([name, description, frequency, updated, state]) => (
                  <tr key={name}>
                    <td>
                      <strong>{name}</strong>
                    </td>
                    <td>{description}</td>
                    <td>{frequency}</td>
                    <td>{updated}</td>
                    <td>
                      <span
                        className={`state state--${state === "正常" ? "success" : "warning"}`}
                      >
                        {state}
                      </span>
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
