import { Plus, Search } from "lucide-react";

export function StrategiesPage() {
  return (
    <div className="page">
      <section aria-labelledby="strategy-list">
        <div className="section-heading section-heading--tools">
          <div>
            <h2 id="strategy-list">策略</h2>
            <span>功能规划中</span>
          </div>
          <div className="tools-row">
            <label className="search-field search-field--compact">
              <Search size={16} />
              <input aria-label="搜索策略" disabled placeholder="搜索策略" />
            </label>
            <button
              className="button button--primary"
              disabled
              title="策略功能尚未开放"
              type="button"
            >
              <Plus size={16} />
              策略
            </button>
          </div>
        </div>
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
              <tr>
                <td className="table-empty" colSpan={6}>
                  策略功能规划中
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
