import { FormEvent, useState } from "react";
import { X } from "lucide-react";

import type { BinanceAccountDraft } from "./types";

type Props = {
  onCancel: () => void;
  onSave: (account: BinanceAccountDraft) => void | Promise<void>;
};

export function AccountBindingDialog({ onCancel, onSave }: Props) {
  const [alias, setAlias] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [apiSecret, setApiSecret] = useState("");
  const [ipWhitelistConfirmed, setIpWhitelistConfirmed] = useState(false);

  function clearSensitiveFields() {
    setApiKey("");
    setApiSecret("");
  }

  function cancel() {
    clearSensitiveFields();
    onCancel();
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      await onSave({ alias, apiKey, apiSecret, ipWhitelistConfirmed });
    } finally {
      clearSensitiveFields();
    }
  }

  const canSubmit =
    alias.trim().length > 0 &&
    apiKey.length >= 8 &&
    apiSecret.length >= 8 &&
    ipWhitelistConfirmed;

  return (
    <div className="modal-backdrop" role="presentation">
      <section
        aria-labelledby="account-binding-title"
        aria-modal="true"
        className="modal account-binding-dialog"
        role="dialog"
      >
        <div className="modal-header">
          <h2 id="account-binding-title">添加B账号</h2>
          <button
            aria-label="关闭"
            className="icon-button"
            onClick={cancel}
            title="关闭"
            type="button"
          >
            <X size={17} />
          </button>
        </div>

        <form onSubmit={submit}>
          <div className="form-grid">
            <label className="field">
              <span>账号别名</span>
              <input
                autoComplete="off"
                onChange={(event) => setAlias(event.target.value)}
                placeholder="例如：主交易账号"
                required
                value={alias}
              />
            </label>
            <label className="field">
              <span>API Key</span>
              <input
                autoComplete="new-password"
                onChange={(event) => setApiKey(event.target.value)}
                required
                type="password"
                value={apiKey}
              />
            </label>
            <label className="field">
              <span>API Secret</span>
              <input
                aria-label="API Secret"
                autoComplete="new-password"
                onChange={(event) => setApiSecret(event.target.value)}
                required
                type="password"
                value={apiSecret}
              />
            </label>
            <label className="security-confirmation">
              <input
                aria-label="已配置固定出口 IP 白名单"
                checked={ipWhitelistConfirmed}
                onChange={(event) =>
                  setIpWhitelistConfirmed(event.target.checked)
                }
                type="checkbox"
              />
              <span>
                <strong>已配置固定出口 IP 白名单</strong>
                <small>凭据仅用于权限验证和交易连接，不保存明文。</small>
              </span>
            </label>
          </div>

          <div className="modal-actions">
            <button
              className="button button--secondary"
              onClick={cancel}
              type="button"
            >
              取消
            </button>
            <button
              className="button button--primary"
              disabled={!canSubmit}
              type="submit"
            >
              保存账号
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}
