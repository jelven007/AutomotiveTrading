import { KeyRound, Mail, ShieldCheck } from "lucide-react";

import { useAuth } from "../features/auth/AuthContext";

const roleLabels: Record<string, string> = {
  tenant_admin: "管理员",
};

export function UserProfilePage() {
  const auth = useAuth();
  const email = auth.claims?.email ?? "未提供邮箱";
  const roles =
    auth.claims?.roles.map((role) => roleLabels[role] ?? role) ?? [];

  return (
    <div className="page user-profile-page">
      <div className="page-heading">
        <div>
          <h1>用户详情</h1>
          <p className="page-description">查看当前登录帐号和安全状态。</p>
        </div>
      </div>

      <section
        className="panel user-profile-panel"
        aria-labelledby="user-account"
      >
        <div className="panel-heading">
          <h2 id="user-account">帐号信息</h2>
        </div>
        <dl className="user-profile-list">
          <div>
            <dt>
              <Mail size={16} /> 登录邮箱
            </dt>
            <dd>{email}</dd>
          </div>
          <div>
            <dt>
              <ShieldCheck size={16} /> 权限
            </dt>
            <dd>{roles.join("、") || "普通用户"}</dd>
          </div>
          <div>
            <dt>
              <KeyRound size={16} /> 动态验证
            </dt>
            <dd>{auth.claims?.mfa_enabled ? "已配置" : "未配置"}</dd>
          </div>
        </dl>
      </section>
    </div>
  );
}
