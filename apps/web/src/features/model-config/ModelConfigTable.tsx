import {
  KeyRound,
  MoreHorizontal,
  PlugZap,
  ShieldCheck,
  Trash2,
} from "lucide-react";

import type { ModelConfiguration } from "./api";

type Props = {
  configurations: ModelConfiguration[];
  canManage: boolean;
  onDelete: (configuration: ModelConfiguration) => void;
  onRotate: (configuration: ModelConfiguration) => void;
  onToggle: (configuration: ModelConfiguration) => void;
};

const providerLabels: Record<ModelConfiguration["providerType"], string> = {
  openai: "OpenAI",
  anthropic: "Anthropic",
  deepseek: "DeepSeek",
  openai_compatible: "兼容接口",
  ollama: "Ollama",
  vllm: "vLLM",
};

export function ModelConfigTable({
  configurations,
  canManage,
  onDelete,
  onRotate,
  onToggle,
}: Props) {
  return (
    <div className="table-scroll">
      <table className="model-table">
        <thead>
          <tr>
            <th>配置</th>
            <th>供应商</th>
            <th>模型</th>
            <th>密钥</th>
            <th>可用环境</th>
            <th>状态</th>
            {canManage && <th aria-label="操作" />}
          </tr>
        </thead>
        <tbody>
          {configurations.map((configuration) => {
            const planned = configuration.availability === "planned";
            return (
              <tr key={configuration.id}>
                <td>
                  <strong>{configuration.name}</strong>
                  <small>{configuration.baseUrl}</small>
                </td>
                <td>{providerLabels[configuration.providerType]}</td>
                <td>{configuration.modelId}</td>
                <td>
                  <span className="secret-state">
                    <ShieldCheck size={13} />
                    {configuration.secretStatus === "configured"
                      ? "已配置"
                      : configuration.secretStatus === "managed"
                        ? "KMS 托管"
                        : "未配置"}
                  </span>
                </td>
                <td>{configuration.allowedEnvironments.join(" / ")}</td>
                <td>
                  {planned ? (
                    <span className="state state--neutral">待开放</span>
                  ) : (
                    <label className="toggle">
                      <input
                        aria-label={`启用 ${configuration.name}`}
                        type="checkbox"
                        checked={configuration.enabled}
                        disabled={!canManage}
                        onChange={() => onToggle(configuration)}
                      />
                      <span />
                    </label>
                  )}
                </td>
                {canManage && (
                  <td>
                    <div className="row-actions">
                      <button
                        className="icon-button icon-button--small"
                        aria-label={`测试 ${configuration.name}`}
                        title={planned ? "待开放" : "测试连接"}
                        disabled={planned}
                      >
                        <PlugZap size={15} />
                      </button>
                      <button
                        className="icon-button icon-button--small"
                        aria-label={`轮换 ${configuration.name} 密钥`}
                        title="轮换密钥"
                        onClick={() => onRotate(configuration)}
                      >
                        <KeyRound size={15} />
                      </button>
                      <button
                        className="icon-button icon-button--small icon-button--danger"
                        aria-label={`删除 ${configuration.name}`}
                        title="删除"
                        onClick={() => onDelete(configuration)}
                      >
                        <Trash2 size={15} />
                      </button>
                      <button
                        className="icon-button icon-button--small"
                        aria-label={`${configuration.name} 更多操作`}
                        title="更多操作"
                      >
                        <MoreHorizontal size={15} />
                      </button>
                    </div>
                  </td>
                )}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
