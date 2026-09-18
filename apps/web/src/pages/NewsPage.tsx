import { Bookmark, Filter, Search } from "lucide-react";

const newsItems = [
  {
    type: "公司公告",
    market: "港股",
    title: "腾讯控股披露最新股份回购进展",
    source: "港交所公告",
    time: "10:18",
    symbols: "00700.HK",
  },
  {
    type: "宏观",
    market: "A 股",
    title: "公开市场操作延续净投放，短端资金利率平稳",
    source: "中国货币网",
    time: "09:46",
    symbols: "沪深全市场",
  },
  {
    type: "财报事件",
    market: "美股",
    title: "Adobe 上调全年订阅收入指引",
    source: "SEC Filing",
    time: "08:32",
    symbols: "ADBE.US",
  },
];

export function NewsPage() {
  return (
    <div className="page">
      <div className="page-heading">
        <div>
          <p className="eyebrow">资讯与事件</p>
          <h1>市场资讯</h1>
          <p className="page-description">
            追踪已去重的信息源，并保留策略可复现的时点快照。
          </p>
        </div>
        <button className="button button--primary">
          <Bookmark size={16} />
          管理订阅
        </button>
      </div>

      <div className="filter-bar">
        <label className="search-field">
          <Search size={17} />
          <input aria-label="搜索资讯" placeholder="搜索标题、标的或来源" />
        </label>
        <button className="button button--secondary">
          <Filter size={16} />
          筛选
        </button>
        <div className="filter-tabs" aria-label="资讯类型">
          <button className="is-active">全部</button>
          <button>新闻</button>
          <button>公告</button>
          <button>研报</button>
          <button>财报</button>
        </div>
      </div>

      <section className="panel list-panel" aria-labelledby="news-stream">
        <div className="panel-heading">
          <div>
            <h2 id="news-stream">实时资讯流</h2>
            <span>最后采集 10:31:08 · 延迟 8 秒</span>
          </div>
        </div>
        <div className="news-list">
          {newsItems.map((item) => (
            <article className="news-row" key={item.title}>
              <time>{item.time}</time>
              <div>
                <div className="tag-row">
                  <span className="tag">{item.market}</span>
                  <span className="tag tag--neutral">{item.type}</span>
                </div>
                <h2>{item.title}</h2>
                <p>
                  {item.source} · {item.symbols}
                </p>
              </div>
              <button
                className="icon-button"
                aria-label={`收藏 ${item.title}`}
                title="收藏"
              >
                <Bookmark size={17} />
              </button>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}
