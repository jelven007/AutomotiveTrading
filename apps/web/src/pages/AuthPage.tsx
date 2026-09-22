import { FormEvent, useState } from "react";
import {
  Eye,
  EyeOff,
  KeyRound,
  LockKeyhole,
  ShieldCheck,
  Workflow,
} from "lucide-react";

import { AuthApiError } from "../features/auth/api";
import { useAuth } from "../features/auth/AuthContext";

type Mode = "login" | "register";

export function AuthPage() {
  const auth = useAuth();
  const [mode, setMode] = useState<Mode>("login");
  const [email, setEmail] = useState(
    () => localStorage.getItem("qt.last_email") ?? "",
  );
  const [password, setPassword] = useState("");
  const [passwordConfirmation, setPasswordConfirmation] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function changeMode(nextMode: Mode) {
    setMode(nextMode);
    setPassword("");
    setPasswordConfirmation("");
    setError(null);
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (mode === "register" && password !== passwordConfirmation) {
      setError("两次输入的密码不一致");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      if (mode === "login") {
        await auth.login({ email, password });
      } else {
        await auth.register({ email, password });
      }
    } catch (caught) {
      setError(
        caught instanceof AuthApiError
          ? authErrorMessage(caught)
          : "身份服务暂时不可用",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="auth-layout">
      <section className="auth-context" aria-label="Quant Desk 安全访问">
        <div className="auth-brand">
          <span className="brand-mark" aria-hidden="true">
            <Workflow size={22} strokeWidth={2.2} />
          </span>
          <span>
            <strong>Quant Desk</strong>
            <small>交易决策中枢</small>
          </span>
        </div>
        <div className="auth-context__content">
          <h1>进入交易工作区</h1>
          <p>安全管理唯一B模拟账号与账户数据。</p>
          <div className="auth-security-list">
            <span>
              <ShieldCheck size={17} />
              权限隔离
            </span>
            <span>
              <LockKeyhole size={17} />
              敏感操作 MFA
            </span>
            <span>
              <KeyRound size={17} />
              凭据本地加密
            </span>
          </div>
        </div>
      </section>

      <section className="auth-form-region">
        <div className="auth-panel">
          <div className="auth-tabs" role="tablist" aria-label="身份入口">
            <button
              aria-selected={mode === "login"}
              className={mode === "login" ? "is-active" : ""}
              onClick={() => changeMode("login")}
              role="tab"
              type="button"
            >
              登录
            </button>
            <button
              aria-selected={mode === "register"}
              className={mode === "register" ? "is-active" : ""}
              onClick={() => changeMode("register")}
              role="tab"
              type="button"
            >
              注册
            </button>
          </div>

          <div className="auth-form-heading">
            <h2>{mode === "login" ? "登录 Quant Desk" : "创建管理帐号"}</h2>
            <p>
              {mode === "login"
                ? "使用邮箱和密码继续。"
                : "注册后即可进入交易工作区。"}
            </p>
          </div>

          <form className="auth-form" onSubmit={submit}>
            <label className="field">
              <span>邮箱</span>
              <input
                autoComplete="email"
                onChange={(event) => setEmail(event.target.value)}
                required
                type="email"
                value={email}
              />
            </label>

            <label className="field">
              <span>密码</span>
              <div className="secret-input">
                <input
                  autoComplete={
                    mode === "login" ? "current-password" : "new-password"
                  }
                  minLength={12}
                  onChange={(event) => setPassword(event.target.value)}
                  required
                  type={showPassword ? "text" : "password"}
                  value={password}
                />
                <button
                  aria-label={showPassword ? "隐藏密码" : "显示密码"}
                  onClick={() => setShowPassword((current) => !current)}
                  title={showPassword ? "隐藏密码" : "显示密码"}
                  type="button"
                >
                  {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </label>

            {mode === "register" && (
              <label className="field">
                <span>确认密码</span>
                <input
                  autoComplete="new-password"
                  minLength={12}
                  onChange={(event) =>
                    setPasswordConfirmation(event.target.value)
                  }
                  required
                  type={showPassword ? "text" : "password"}
                  value={passwordConfirmation}
                />
              </label>
            )}

            {error && (
              <div className="auth-error" role="alert">
                {error}
              </div>
            )}

            <button
              className="button button--primary button--full auth-submit"
              disabled={busy}
              type="submit"
            >
              {busy ? "正在验证..." : mode === "login" ? "登录" : "创建并登录"}
            </button>
          </form>
        </div>
      </section>
    </main>
  );
}

function authErrorMessage(error: AuthApiError): string {
  if (error.status === 401) {
    return "邮箱或密码不正确";
  }
  if (error.code === "registration.closed") {
    return "系统已完成初始化，请使用所有者账号登录";
  }
  if (error.code === "registration.invalid") {
    return error.message || "该邮箱已注册";
  }
  return error.message;
}
