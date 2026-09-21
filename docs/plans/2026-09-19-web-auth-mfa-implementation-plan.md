# Web Authentication and MFA Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**范围修订（2026-09-21）：** 币安帐号绑定和只读查询不再要求 MFA。本文中的
绑定前 MFA 步骤已失效；MFA 仅用于
[`QT-DES-BIN-SIMPLE-001`](2026-09-21-binance-single-account-phased-design.md)
阶段二的短时交易会话。

**Goal:** 为 Quant Desk Web 接通登录、注册、会话刷新和 TOTP MFA，并在添加币安真实帐号前强制完成近期 MFA。

**Architecture:** 使用 React Context 统一管理访问令牌与刷新令牌，应用入口根据认证状态显示登录页或业务工作台。普通页面只要求登录，添加币安帐号时按需弹出 MFA 验证；首次使用可在同一弹窗配置 TOTP。

**Tech Stack:** React 19、React Router 7、TypeScript、Vitest、Testing Library、Identity Tenant REST API。

---

### Task 1: 认证 API 与会话状态

**Files:**
- Create: `apps/web/src/features/auth/api.ts`
- Create: `apps/web/src/features/auth/session.ts`
- Create: `apps/web/src/features/auth/AuthProvider.tsx`
- Test: `apps/web/src/features/auth/AuthProvider.test.tsx`

**Steps:**
1. 为登录、注册、刷新、退出、TOTP 配置和验证定义类型化 API。
2. 增加 JWT Claim 解析、过期判断、近期 MFA 判断和会话存储。
3. 实现 Auth Provider，启动时恢复或刷新会话。
4. 验证登录、刷新失败清理会话和 MFA Token 替换。

### Task 2: 登录与注册页面

**Files:**
- Create: `apps/web/src/pages/AuthPage.tsx`
- Modify: `apps/web/src/app/router.tsx`
- Modify: `apps/web/src/styles/tokens.css`
- Test: `apps/web/src/features/auth/AuthPage.test.tsx`

**Steps:**
1. 实现登录和注册分段表单。
2. 登录要求邮箱、密码和租户 ID。
3. 注册要求姓名、组织、邮箱和至少 12 位密码。
4. 应用入口增加加载态和未登录门禁。
5. 补充桌面与移动端布局。

### Task 3: TOTP MFA

**Files:**
- Create: `apps/web/src/features/auth/MfaDialog.tsx`
- Modify: `apps/web/src/pages/trading/TradingWorkspace.tsx`
- Modify: `apps/web/src/styles/tokens.css`
- Test: `apps/web/src/features/auth/MfaDialog.test.tsx`
- Test: `apps/web/src/features/trading/TradingWorkspace.test.tsx`

**Steps:**
1. 实现六位动态验证码输入和验证。
2. 支持首次申请 TOTP Secret 和复制配置 URI。
3. 添加币安帐号前检查角色及 MFA 时间。
4. MFA 成功后更新访问令牌并打开帐号绑定表单。
5. 验证无 MFA、MFA 成功和验证失败流程。

### Task 4: 会话入口与开发代理

**Files:**
- Modify: `apps/web/src/app/AppShell.tsx`
- Modify: `apps/web/vite.config.ts`
- Test: `apps/web/src/app/AppShell.test.tsx`

**Steps:**
1. Appbar 展示当前租户并提供退出登录。
2. 本地 Vite 代理 `/api/v1/auth` 和 `/api/v1/tenants` 到身份服务。
3. 保持 `/api/v1/trading` 代理及固定 6173 端口不变。

### Task 5: 验证

**Steps:**
1. 运行 Web 单元测试。
2. 运行 TypeScript、ESLint 和生产构建。
3. 启动本地服务并用浏览器验证桌面、移动端登录及 MFA 弹窗。
4. 确认敏感输入不会出现在页面回显和错误消息中。
