import { FormEvent, useState } from "react";
import { Eye, EyeOff, X } from "lucide-react";

import type { CreateModelConfiguration, ProviderType } from "./api";

type Props = {
  onCancel: () => void;
  onSave: (configuration: CreateModelConfiguration) => void;
};

const providerDefaults: Record<ProviderType, string> = {
  openai: "https://api.openai.com/v1",
  anthropic: "https://api.anthropic.com/v1",
  deepseek: "https://api.deepseek.com/v1",
  openai_compatible: "https://api.example.com/v1",
  ollama: "https://ollama.example.com/v1",
  vllm: "https://vllm.example.com/v1",
};

export function ModelConfigForm({ onCancel, onSave }: Props) {
  const [providerType, setProviderType] = useState<ProviderType>("openai");
  const [name, setName] = useState("");
  const [baseUrl, setBaseUrl] = useState(providerDefaults.openai);
  const [modelId, setModelId] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [showSecret, setShowSecret] = useState(false);
  const [enabled, setEnabled] = useState(false);
  const planned = providerType === "ollama" || providerType === "vllm";

  function changeProvider(value: ProviderType) {
    setProviderType(value);
    setBaseUrl(providerDefaults[value]);
    if (value === "ollama" || value === "vllm") {
      setEnabled(false);
    }
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onSave({
      name,
      providerType,
      baseUrl,
      modelId,
      apiKey,
      enabled,
      allowedEnvironments: ["backtest", "simulation"],
    });
    setApiKey("");
  }

  return (
    <div className="modal-backdrop" role="presentation">
      <section
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="model-form-title"
      >
        <div className="modal-header">
          <div>
            <p className="eyebrow">租户级凭据</p>
            <h2 id="model-form-title">新增模型服务</h2>
          </div>
          <button
            className="icon-button"
            aria-label="关闭"
            title="关闭"
            onClick={onCancel}
          >
            <X size={17} />
          </button>
        </div>

        <form onSubmit={submit}>
          <div className="form-grid">
            <label className="field">
              <span>配置名称</span>
              <input
                required
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="例如：研究主模型"
              />
            </label>
            <label className="field">
              <span>供应商类型</span>
              <select
                value={providerType}
                onChange={(event) =>
                  changeProvider(event.target.value as ProviderType)
                }
              >
                <option value="openai">OpenAI</option>
                <option value="anthropic">Anthropic</option>
                <option value="deepseek">DeepSeek</option>
                <option value="openai_compatible">OpenAI Compatible</option>
                <option value="ollama">Ollama（待开放）</option>
                <option value="vllm">vLLM（待开放）</option>
              </select>
            </label>
            <label className="field field--wide">
              <span>Base URL</span>
              <input
                required
                type="url"
                value={baseUrl}
                onChange={(event) => setBaseUrl(event.target.value)}
              />
            </label>
            <label className="field">
              <span>模型 ID</span>
              <input
                required
                value={modelId}
                onChange={(event) => setModelId(event.target.value)}
                placeholder="model-name"
              />
            </label>
            <label className="field">
              <span>API Key</span>
              <span className="secret-input">
                <input
                  required
                  type={showSecret ? "text" : "password"}
                  value={apiKey}
                  onChange={(event) => setApiKey(event.target.value)}
                  autoComplete="new-password"
                />
                <button
                  type="button"
                  aria-label={showSecret ? "隐藏密钥" : "显示密钥"}
                  title={showSecret ? "隐藏密钥" : "显示密钥"}
                  onClick={() => setShowSecret((current) => !current)}
                >
                  {showSecret ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </span>
            </label>
            <label className="field">
              <span>请求超时</span>
              <span className="input-suffix">
                <input
                  type="number"
                  defaultValue="30000"
                  min="1000"
                  step="1000"
                />
                <span>ms</span>
              </span>
            </label>
            <label className="field">
              <span>最大并发</span>
              <input type="number" defaultValue="10" min="1" max="100" />
            </label>
          </div>

          <div className="form-option">
            <span>
              <strong>保存后启用</strong>
              <small>
                {planned ? "待开放供应商暂不可启用" : "启用后可供策略选择"}
              </small>
            </span>
            <label className="toggle">
              <input
                aria-label="保存后启用"
                type="checkbox"
                checked={enabled}
                disabled={planned}
                onChange={(event) => setEnabled(event.target.checked)}
              />
              <span />
            </label>
          </div>

          <div className="modal-actions">
            <button
              type="button"
              className="button button--secondary"
              onClick={onCancel}
            >
              取消
            </button>
            <button type="submit" className="button button--primary">
              保存配置
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}
