import {
  AlertCircle,
  KeyRound,
  Plus,
  RefreshCw,
  RotateCcw,
  Trash2,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { BtcSpotPriceCard } from "../market/BtcSpotPriceCard";
import { useAuth } from "../auth/AuthContext";
import { AccountBindingDialog } from "./AccountBindingDialog";
import { BinanceAccountOverview } from "./BinanceAccountOverview";
import {
  deleteBinanceAccount,
  fetchBinanceOverview,
  replaceBinanceAccount,
  TradingApiError,
} from "./api";
import type { BinanceAccountDraft, BinanceOverview } from "./types";

// 总资产面板：读取真实币安 overview，并复用绑定 / 重新绑定 / 删除流程
export function BinanceAssetsPanel() {
  const auth = useAuth();
  const [overview, setOverview] = useState<BinanceOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [showBinding, setShowBinding] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  const loadOverview = useCallback(
    async (refresh = false) => {
      if (!auth.accessToken) {
        setLoading(false);
        return;
      }
      setLoading(true);
      try {
        setOverview(await fetchBinanceOverview(auth.accessToken, refresh));
        setNotice(null);
      } catch (error) {
        // 未绑定账号属于正常空态，其余错误才作为提示展示
        if (
          error instanceof TradingApiError &&
          error.code === "binance.account_missing"
        ) {
          setOverview(null);
          setNotice(null);
        } else {
          setNotice(
            error instanceof Error ? error.message : "币安账户数据加载失败",
          );
        }
      } finally {
        setLoading(false);
      }
    },
    [auth.accessToken],
  );

  useEffect(() => {
    void loadOverview();
  }, [loadOverview]);

  async function saveAccount(draft: BinanceAccountDraft) {
    if (!auth.accessToken) {
      setNotice("登录会话不可用，账号未保存。");
      return;
    }
    try {
      await replaceBinanceAccount(auth.accessToken, draft);
      await loadOverview(true);
      setShowBinding(false);
      setNotice(`${draft.alias} 已连接。`);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "币安账号保存失败。");
    }
  }

  async function removeAccount() {
    if (!auth.accessToken || !window.confirm("确认删除当前币安账号？")) {
      return;
    }
    try {
      await deleteBinanceAccount(auth.accessToken);
      setOverview(null);
      setNotice("币安账号已删除。");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "币安账号删除失败。");
    }
  }

  return (
    <section className="binance-assets" aria-labelledby="binance-assets">
      <div className="section-heading">
        <div>
          <h2 id="binance-assets">总资产</h2>
          {overview ? (
            <span>
              {overview.account.alias} · 数据时间 {formatTime(overview.asOf)}
            </span>
          ) : (
            <span>币安现货 / U 本位合约</span>
          )}
        </div>
        {overview && (
          <div className="page-actions">
            <button
              className="button button--secondary"
              disabled={loading}
              onClick={() => void loadOverview(true)}
              type="button"
            >
              <RefreshCw
                className={loading ? "is-spinning" : undefined}
                size={16}
              />
              刷新
            </button>
            <button
              className="button button--secondary"
              onClick={() => setShowBinding(true)}
              type="button"
            >
              <RotateCcw size={16} />
              重新绑定
            </button>
            <button
              className="button button--danger"
              onClick={() => void removeAccount()}
              type="button"
            >
              <Trash2 size={16} />
              删除账号
            </button>
          </div>
        )}
      </div>

      {notice && (
        <div className="inline-notice" role="status">
          <AlertCircle size={16} />
          <span>{notice}</span>
          <button aria-label="关闭提示" onClick={() => setNotice(null)}>
            关闭
          </button>
        </div>
      )}

      {/* 总资产内容区拆左右两栏：左侧账户资产 / 绑定入口，右侧 BTC/USDT 实时价 */}
      <div className="trading-split">
        <div className="trading-split__main">
          {loading && !overview ? (
            <div className="binance-page-state" role="status">
              <RefreshCw className="is-spinning" size={18} />
              正在读取账户
            </div>
          ) : overview ? (
            <BinanceAccountOverview overview={overview} />
          ) : (
            <div className="binance-empty">
              <KeyRound size={22} />
              <h2>尚未绑定币安账号</h2>
              <button
                className="button button--primary"
                onClick={() => setShowBinding(true)}
                type="button"
              >
                <Plus size={16} />
                账号
              </button>
            </div>
          )}
        </div>
        <div className="trading-split__aside">
          <BtcSpotPriceCard />
        </div>
      </div>

      {showBinding && (
        <AccountBindingDialog
          onCancel={() => setShowBinding(false)}
          onSave={saveAccount}
        />
      )}
    </section>
  );
}

function formatTime(value: string): string {
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}
