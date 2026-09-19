import { FormEvent, useEffect, useRef, useState } from "react";
import { Copy, KeyRound, LoaderCircle, ShieldCheck, X } from "lucide-react";
import QRCode from "qrcode";

import { AuthApiError, TotpEnrollment } from "./api";
import { useAuth } from "./AuthContext";

type Props = {
  onCancel: () => void;
  onVerified: () => void;
};

export function MfaDialog({ onCancel, onVerified }: Props) {
  const auth = useAuth();
  const isEnrolled = auth.claims?.mfa_enabled === true;
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [code, setCode] = useState("");
  const [enrollment, setEnrollment] = useState<TotpEnrollment | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!enrollment || !canvasRef.current) {
      return;
    }
    void QRCode.toCanvas(canvasRef.current, enrollment.provisioningUri, {
      width: 184,
      margin: 1,
      color: { dark: "#18212b", light: "#ffffff" },
    }).catch(() => setError("二维码生成失败，请使用配置密钥"));
  }, [enrollment]);

  async function beginEnrollment() {
    setBusy(true);
    setError(null);
    try {
      setEnrollment(await auth.enrollMfa());
    } catch (caught) {
      setError(mfaErrorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  async function verify(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await auth.verifyMfa(code);
      onVerified();
    } catch (caught) {
      setError(mfaErrorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  async function copySecret() {
    if (!enrollment) {
      return;
    }
    await navigator.clipboard.writeText(enrollment.secret);
    setCopied(true);
  }

  return (
    <div className="modal-backdrop" role="presentation">
      <section
        aria-labelledby="mfa-title"
        aria-modal="true"
        className="modal mfa-dialog"
        role="dialog"
      >
        <div className="modal-header">
          <div>
            <p className="eyebrow">敏感操作确认</p>
            <h2 id="mfa-title">验证身份</h2>
          </div>
          <button
            aria-label="关闭"
            className="icon-button"
            onClick={onCancel}
            title="关闭"
            type="button"
          >
            <X size={17} />
          </button>
        </div>

        <form onSubmit={verify}>
          {enrollment ? (
            <div className="mfa-enrollment">
              <canvas aria-label="身份验证器二维码" ref={canvasRef} />
              <div>
                <strong>配置密钥</strong>
                <div className="mfa-secret">
                  <code>{enrollment.secret}</code>
                  <button
                    aria-label="复制配置密钥"
                    className="icon-button icon-button--small"
                    onClick={() => void copySecret()}
                    title="复制配置密钥"
                    type="button"
                  >
                    <Copy size={14} />
                  </button>
                </div>
                {copied && <small role="status">已复制</small>}
              </div>
            </div>
          ) : (
            <div className="mfa-status">
              <ShieldCheck size={19} />
              <span>
                {isEnrolled
                  ? "输入身份验证器生成的六位验证码"
                  : "此帐号尚未配置身份验证器"}
              </span>
            </div>
          )}

          <label className="field">
            <span>动态验证码</span>
            <input
              autoComplete="one-time-code"
              autoFocus
              inputMode="numeric"
              maxLength={6}
              onChange={(event) =>
                setCode(event.target.value.replace(/\D/g, "").slice(0, 6))
              }
              pattern="\d{6}"
              placeholder="000000"
              required
              value={code}
            />
          </label>

          {error && (
            <div className="auth-error" role="alert">
              {error}
            </div>
          )}

          <div className="modal-actions modal-actions--split">
            {!isEnrolled && !enrollment && (
              <button
                className="button button--secondary"
                disabled={busy}
                onClick={() => void beginEnrollment()}
                type="button"
              >
                <KeyRound size={15} />
                配置验证器
              </button>
            )}
            <div className="modal-actions__end">
              <button
                className="button button--secondary"
                disabled={busy}
                onClick={onCancel}
                type="button"
              >
                取消
              </button>
              <button
                className="button button--primary"
                disabled={busy || code.length !== 6}
                type="submit"
              >
                {busy && <LoaderCircle className="spin" size={15} />}
                验证并继续
              </button>
            </div>
          </div>
        </form>
      </section>
    </div>
  );
}

function mfaErrorMessage(error: unknown): string {
  if (error instanceof AuthApiError) {
    if (error.status === 401) {
      return error.message.includes("enrollment")
        ? "尚未配置身份验证器"
        : "验证码无效或已过期";
    }
    return error.message;
  }
  return error instanceof Error ? error.message : "身份验证失败";
}
