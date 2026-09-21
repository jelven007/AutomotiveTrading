import { Plus, Search } from "lucide-react";
import { useMemo, useState } from "react";

import { BinanceAssetsPanel } from "../features/trading/BinanceAssetsPanel";

type Order = {
  id: string;
  symbol: string;
  side: string;
  type: string;
  price: string;
  quantity: string;
  status: string;
};

// 当前订单：阶段二开放下单 / 撤单后接入真实数据，阶段一先以空列表呈现结构
const orders: Order[] = [];

export function TradingPage() {
  const [keyword, setKeyword] = useState("");

  // 按合约名模糊过滤，忽略大小写与首尾空白
  const filtered = useMemo(() => {
    const term = keyword.trim().toLowerCase();
    if (!term) {
      return orders;
    }
    return orders.filter((item) => item.symbol.toLowerCase().includes(term));
  }, [keyword]);

  return (
    <div className="page">
      <BinanceAssetsPanel />

      <section aria-labelledby="open-orders">
        <div className="section-heading section-heading--tools">
          <div>
            <h2 id="open-orders">当前订单</h2>
            <span>按下单时间排序</span>
          </div>
          <div className="tools-row">
            <label className="search-field search-field--compact">
              <Search size={16} />
              <input
                aria-label="搜索订单"
                placeholder="搜索订单"
                value={keyword}
                onChange={(event) => setKeyword(event.target.value)}
              />
            </label>
            <button className="button button--primary" type="button">
              <Plus size={16} />
              订单
            </button>
          </div>
        </div>
        {filtered.length === 0 ? (
          <div className="binance-section-state">
            {orders.length === 0 ? "当前没有进行中的订单" : "没有匹配的订单"}
          </div>
        ) : (
          <div className="market-grid">
            {filtered.map((order) => (
              <OrderCard key={order.id} order={order} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

// 订单卡片：复用首页行情卡片的 market-tile 外框，保证全站卡片风格一致
function OrderCard({ order }: { order: Order }) {
  const isBuy = order.side === "买入";
  return (
    <article className="market-tile">
      <div className="tile-topline">
        <div>
          <strong>{order.symbol}</strong>
          <small>{order.type}</small>
        </div>
        <span className={`state state--${isBuy ? "success" : "warning"}`}>
          {order.side}
        </span>
      </div>
      <div className="market-value-row">
        <div>
          <span className="market-value">{order.price}</span>
          <span className="change change--muted">数量 {order.quantity}</span>
        </div>
      </div>
      <small className="market-time">{order.status}</small>
    </article>
  );
}
