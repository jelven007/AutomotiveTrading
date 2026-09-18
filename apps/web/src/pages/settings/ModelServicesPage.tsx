import { KeyRound, Plus, ShieldAlert } from "lucide-react";
import { useState } from "react";

import { ModelConfigForm } from "../../features/model-config/ModelConfigForm";
import { ModelConfigTable } from "../../features/model-config/ModelConfigTable";
import type {
  CreateModelConfiguration,
  ModelConfiguration,
  UserRole,
} from "../../features/model-config/api";

const initialConfigurations: ModelConfiguration[] = [
  {
    id: "model-openai-primary",
    name: "生产决策模型",
    providerType: "openai",
    baseUrl: "https://api.openai.com/v1",
    modelId: "gpt-production",
    secretStatus: "managed",
    availability: "available",
    enabled: true,
    healthStatus: "healthy",
    allowedEnvironments: ["backtest", "simulation"],
  },
  {
    id: "model-deepseek-fallback",
    name: "DeepSeek 备用",
    providerType: "deepseek",
    baseUrl: "https://api.deepseek.com/v1",
    modelId: "deepseek-chat",
    secretStatus: "managed",
    availability: "available",
    enabled: false,
    healthStatus: "untested",
    allowedEnvironments: ["backtest"],
  },
  {
    id: "model-ollama-planned",
    name: "本地 Ollama",
    providerType: "ollama",
    baseUrl: "https://ollama.example.com/v1",
    modelId: "qwen-local",
    secretStatus: "missing",
    availability: "planned",
    enabled: false,
    healthStatus: "untested",
    allowedEnvironments: ["backtest"],
  },
];

type Props = {
  role?: UserRole;
};

export function ModelServicesPage({ role = "tenant_admin" }: Props) {
  const [configurations, setConfigurations] = useState(initialConfigurations);
  const [showForm, setShowForm] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<ModelConfiguration | null>(
    null,
  );
  const [notice, setNotice] = useState<string | null>(null);
  const canManage = role === "tenant_admin";

  function saveConfiguration(command: CreateModelConfiguration) {
    const planned =
      command.providerType === "ollama" || command.providerType === "vllm";
    const created: ModelConfiguration = {
      id: crypto.randomUUID(),
      name: command.name,
      providerType: command.providerType,
      baseUrl: command.baseUrl,
      modelId: command.modelId,
      secretStatus: "configured",
      availability: planned ? "planned" : "available",
      enabled: planned ? false : command.enabled,
      healthStatus: "untested",
      allowedEnvironments: command.allowedEnvironments,
    };
    setConfigurations((current) => [...current, created]);
    setShowForm(false);
    setNotice(`${created.name} 已保存，密钥已转交安全存储。`);
  }

  function toggleConfiguration(configuration: ModelConfiguration) {
    setConfigurations((current) =>
      current.map((item) =>
        item.id === configuration.id
          ? { ...item, enabled: !item.enabled }
          : item,
      ),
    );
  }

  function rotateSecret(configuration: ModelConfiguration) {
    setNotice(`${configuration.name} 的密钥轮换流程已启动。`);
  }

  function deleteConfiguration() {
    if (!deleteTarget) {
      return;
    }
    setConfigurations((current) =>
      current.filter((item) => item.id !== deleteTarget.id),
    );
    setNotice(`${deleteTarget.name} 已删除。`);
    setDeleteTarget(null);
  }

  return (
    <div className="page">
      <div className="settings-breadcrumb">租户设置 / 模型服务</div>
      <div className="page-heading">
        <div>
          <p className="eyebrow">AI 基础设施</p>
          <h1>模型服务</h1>
          <p className="page-description">
            管理租户可用的模型端点、凭据状态和执行环境。
          </p>
        </div>
        {canManage && (
          <button
            className="button button--primary"
            onClick={() => setShowForm(true)}
          >
            <Plus size={16} />
            新增模型服务
          </button>
        )}
      </div>

      {!canManage && (
        <div className="permission-notice">
          <ShieldAlert size={17} />
          <span>
            <strong>仅可查看与选择已启用模型</strong>
            <small>模型凭据和管理操作仅对租户管理员开放。</small>
          </span>
        </div>
      )}

      {notice && (
        <div className="inline-notice" role="status">
          <KeyRound size={16} />
          {notice}
          <button aria-label="关闭提示" onClick={() => setNotice(null)}>
            关闭
          </button>
        </div>
      )}

      <section
        className="panel list-panel"
        aria-labelledby="model-service-list"
      >
        <div className="panel-heading">
          <div>
            <h2 id="model-service-list">服务配置</h2>
            <span>{configurations.length} 个配置 · 凭据由 KMS 隔离托管</span>
          </div>
        </div>
        <ModelConfigTable
          configurations={configurations}
          canManage={canManage}
          onDelete={setDeleteTarget}
          onRotate={rotateSecret}
          onToggle={toggleConfiguration}
        />
      </section>

      {showForm && (
        <ModelConfigForm
          onCancel={() => setShowForm(false)}
          onSave={saveConfiguration}
        />
      )}

      {deleteTarget && (
        <div className="modal-backdrop" role="presentation">
          <section
            className="confirm-dialog"
            role="alertdialog"
            aria-modal="true"
            aria-labelledby="delete-model-title"
          >
            <span className="attention-icon attention-icon--danger">
              <ShieldAlert size={19} />
            </span>
            <h2 id="delete-model-title">删除模型配置？</h2>
            <p>
              删除前系统会检查策略引用。此操作不会在页面中显示或导出已托管密钥。
            </p>
            <div className="modal-actions">
              <button
                className="button button--secondary"
                onClick={() => setDeleteTarget(null)}
              >
                取消
              </button>
              <button
                className="button button--danger"
                onClick={deleteConfiguration}
              >
                确认删除
              </button>
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
