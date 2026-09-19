import { FormEvent, useState } from "react";
import { KeyRound, X } from "lucide-react";

import type {
  BinanceScope,
  CredentialType,
  MarketGroup,
  TradingAccountDraft,
  TradingProvider,
} from "./types";

type Props = {
  marketGroup: MarketGroup;
  providers: TradingProvider[];
  onCancel: () => void;
  onSave: (account: TradingAccountDraft) => void;
};

const providerLabels: Record<TradingProvider, string> = {
  tonghuashun: "同花顺",
  caixin: "财信证券",
  futu: "富途",
  longbridge: "长桥",
  binance: "币安",
};

const scopeOptions: Array<{ value: BinanceScope; label: string }> = [
  { value: "spot", label: "现货" },
  { value: "cross_margin", label: "全仓杠杆" },
  { value: "isolated_margin", label: "逐仓杠杆" },
  { value: "usdm_futures", label: "U 本位永续" },
];

const secretLabels: Record<CredentialType, string> = {
  ed25519: "Ed25519 私钥",
  hmac: "HMAC Secret",
  rsa: "RSA 私钥",
};

export function AccountBindingDialog({
  marketGroup,
  providers,
  onCancel,
  onSave,
}: Props) {
  const isBinance = marketGroup === "binance";
  const [alias, setAlias] = useState("");
  const [provider, setProvider] = useState<TradingProvider>(providers[0]);
  const [credentialType, setCredentialType] =
    useState<CredentialType>("ed25519");
  const [apiKey, setApiKey] = useState("");
  const [privateKeyOrSecret, setPrivateKeyOrSecret] = useState("");
  const [enabledScopes, setEnabledScopes] = useState<BinanceScope[]>(["spot"]);
  const [isolatedSymbols, setIsolatedSymbols] = useState("");
  const [ipWhitelistConfirmed, setIpWhitelistConfirmed] = useState(false);

  function clearSensitiveFields() {
    setApiKey("");
    setPrivateKeyOrSecret("");
  }

  function cancel() {
    clearSensitiveFields();
    onCancel();
  }

  function toggleScope(scope: BinanceScope) {
    setEnabledScopes((current) =>
      current.includes(scope)
        ? current.filter((item) => item !== scope)
        : [...current, scope],
    );
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onSave({
      alias,
      marketGroup,
      provider,
      environment: "production",
      credentialType: isBinance ? credentialType : undefined,
      apiKey: isBinance ? apiKey : undefined,
      privateKeyOrSecret: isBinance ? privateKeyOrSecret : undefined,
      enabledScopes: isBinance ? enabledScopes : [],
      isolatedSymbols:
        isBinance && enabledScopes.includes("isolated_margin")
          ? isolatedSymbols
              .split(",")
              .map((symbol) => symbol.trim().toUpperCase())
              .filter(Boolean)
          : [],
      ipWhitelistConfirmed: isBinance ? ipWhitelistConfirmed : true,
    });
    clearSensitiveFields();
  }

  const binanceReady =
    apiKey.length >= 8 &&
    privateKeyOrSecret.length >= 8 &&
    enabledScopes.length > 0 &&
    (!enabledScopes.includes("isolated_margin") ||
      isolatedSymbols.trim().length > 0) &&
    ipWhitelistConfirmed;

  return (
    <div className="modal-backdrop" role="presentation">
      <section
        className="modal account-binding-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="account-binding-title"
      >
        <div className="modal-header">
          <div>
            <p className="eyebrow">生产帐号</p>
            <h2 id="account-binding-title">添加交易帐号</h2>
          </div>
          <button
            className="icon-button"
            aria-label="关闭"
            title="关闭"
            onClick={cancel}
          >
            <X size={17} />
          </button>
        </div>

        <form onSubmit={submit}>
          <div className="form-grid">
            <label className="field">
              <span>帐号别名</span>
              <input
                required
                value={alias}
                onChange={(event) => setAlias(event.target.value)}
                autoComplete="off"
                placeholder="例如：主交易帐号"
              />
            </label>
            <label className="field">
              <span>交易通道</span>
              <select
                value={provider}
                onChange={(event) =>
                  setProvider(event.target.value as TradingProvider)
                }
              >
                {providers.map((item) => (
                  <option key={item} value={item}>
                    {providerLabels[item]}
                  </option>
                ))}
              </select>
            </label>

            {isBinance ? (
              <>
                <label className="field">
                  <span>凭据类型</span>
                  <select
                    value={credentialType}
                    onChange={(event) =>
                      setCredentialType(event.target.value as CredentialType)
                    }
                  >
                    <option value="ed25519">Ed25519（推荐）</option>
                    <option value="hmac">HMAC-SHA256</option>
                    <option value="rsa">RSA</option>
                  </select>
                </label>
                <label className="field">
                  <span>API Key</span>
                  <input
                    required
                    type="password"
                    value={apiKey}
                    onChange={(event) => setApiKey(event.target.value)}
                    autoComplete="new-password"
                  />
                </label>
                <label className="field field--wide">
                  <span>{secretLabels[credentialType]}</span>
                  <textarea
                    required
                    aria-label={secretLabels[credentialType]}
                    value={privateKeyOrSecret}
                    onChange={(event) =>
                      setPrivateKeyOrSecret(event.target.value)
                    }
                    autoComplete="new-password"
                    rows={4}
                  />
                </label>
                <fieldset className="scope-fieldset field--wide">
                  <legend>帐号 Scope</legend>
                  <div className="scope-options">
                    {scopeOptions.map((scope) => (
                      <label key={scope.value}>
                        <input
                          type="checkbox"
                          checked={enabledScopes.includes(scope.value)}
                          onChange={() => toggleScope(scope.value)}
                        />
                        <span>{scope.label}</span>
                      </label>
                    ))}
                  </div>
                </fieldset>
                {enabledScopes.includes("isolated_margin") && (
                  <label className="field field--wide">
                    <span>逐仓交易对</span>
                    <input
                      required
                      value={isolatedSymbols}
                      onChange={(event) =>
                        setIsolatedSymbols(event.target.value)
                      }
                      autoComplete="off"
                      placeholder="BTCUSDT, ETHUSDT"
                    />
                  </label>
                )}
                <label className="security-confirmation field--wide">
                  <input
                    aria-label="已配置固定出口 IP 白名单"
                    type="checkbox"
                    checked={ipWhitelistConfirmed}
                    onChange={(event) =>
                      setIpWhitelistConfirmed(event.target.checked)
                    }
                  />
                  <span>
                    <strong>已配置固定出口 IP 白名单</strong>
                    <small>系统还会检查提现权限，检测到后将拒绝绑定。</small>
                  </span>
                </label>
              </>
            ) : (
              <div className="connector-notice field--wide">
                <KeyRound size={17} />
                <span>
                  <strong>等待正式通道授权</strong>
                  <small>帐号将保存为待授权状态，不能连接或提交订单。</small>
                </span>
              </div>
            )}
          </div>

          <div className="modal-actions">
            <button
              type="button"
              className="button button--secondary"
              onClick={cancel}
            >
              取消
            </button>
            <button
              type="submit"
              className="button button--primary"
              disabled={!alias || (isBinance && !binanceReady)}
            >
              {isBinance ? "保存为只读帐号" : "保存帐号"}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}
