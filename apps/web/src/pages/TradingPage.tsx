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
            <h2 id="open-orders">订单</h2>
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
            <button
              className="button button--primary"
              disabled
              title="订单功能尚未开放"
              type="button"
            >
              <Plus size={16} />
              订单
            </button>
          </div>
        </div>
        <div className="table-scroll list-panel">
          <table>
            <thead>
              <tr>
                <th>合约</th>
                <th>方向</th>
                <th>类型</th>
                <th>价格</th>
                <th>数量</th>
                <th>状态</th>
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 ? (
                <tr>
                  <td className="table-empty" colSpan={6}>
                    {orders.length === 0
                      ? "当前没有进行中的订单"
                      : "没有匹配的订单"}
                  </td>
                </tr>
              ) : (
                filtered.map((order) => (
                  <OrderRow key={order.id} order={order} />
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

// 订单列表行：与策略页共用表格结构和状态标签
function OrderRow({ order }: { order: Order }) {
  const isBuy = order.side === "买入";
  return (
    <tr>
      <td>
        <strong>{order.symbol}</strong>
      </td>
      <td>
        <span className={`state state--${isBuy ? "success" : "warning"}`}>
          {order.side}
        </span>
      </td>
      <td>{order.type}</td>
      <td>{order.price}</td>
      <td>{order.quantity}</td>
      <td className="row-muted">{order.status}</td>
    </tr>
  );
}
