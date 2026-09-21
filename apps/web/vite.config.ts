import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  server: {
    // 本地开发固定端口 8080，strictPort 防止端口占用时静默改用其他端口
    host: "0.0.0.0",
    port: 8080,
    strictPort: true,
    proxy: {
      "/api/v1/auth": "http://127.0.0.1:8001",
      "/api/v1/trading": "http://127.0.0.1:8004",
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: "./src/test/setup.ts",
    css: true,
  },
});
