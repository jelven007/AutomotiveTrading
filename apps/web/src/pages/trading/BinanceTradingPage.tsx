import {
  AlertCircle,
  KeyRound,
  Plus,
  RefreshCw,
  RotateCcw,
  Trash2,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { useAuth } from "../../features/auth/AuthContext";
import { AccountBindingDialog } from "../../features/trading/AccountBindingDialog";
import { BinanceAccountOverview } from "../../features/trading/BinanceAccountOverview";
import {
  deleteBinanceAccount,
  fetchBinanceOverview,
  replaceBinanceAccount,
  TradingApiError,
} from "../../features/trading/api";
import type {
  BinanceAccountDraft,
  BinanceOverview,
} from "../../features/trading/types";

export function BinanceTradingPage() {
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
    <div className="page binance-account-page">
      <header className="binance-account-header">
        <div>
          <h1>币安账户</h1>
          {overview && (
            <div className="binance-account-identity">
              <strong>{overview.account.alias}</strong>
              <span>{overview.account.apiKeyFingerprint}</span>
              <span className="state state--success">已连接</span>
            </div>
          )}
        </div>
        <div className="page-actions">
          {overview && (
            <>
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
            </>
          )}
        </div>
      </header>

      {notice && (
        <div className="inline-notice" role="status">
          <AlertCircle size={16} />
          <span>{notice}</span>
          <button aria-label="关闭提示" onClick={() => setNotice(null)}>
            关闭
          </button>
        </div>
      )}

      {loading && !overview ? (
        <div className="binance-page-state" role="status">
          <RefreshCw className="is-spinning" size={18} />
          正在读取账户
        </div>
      ) : overview ? (
        <>
          <div className="binance-account-meta">
            <span>
              <KeyRound size={15} />
              权限最近验证于 {formatTime(overview.account.lastVerifiedAt)}
            </span>
            <span>数据时间 {formatTime(overview.asOf)}</span>
          </div>
          <BinanceAccountOverview overview={overview} />
        </>
      ) : (
        <section className="binance-empty">
          <KeyRound size={22} />
          <h2>尚未绑定币安账号</h2>
          <button
            className="button button--primary"
            onClick={() => setShowBinding(true)}
            type="button"
          >
            <Plus size={16} />
            添加账号
          </button>
        </section>
      )}

      {showBinding && (
        <AccountBindingDialog
          onCancel={() => setShowBinding(false)}
          onSave={saveAccount}
        />
      )}
    </div>
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
