import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// During development the control-plane API is proxied so the SPA can call /api/*
// without CORS. In production both are served behind the same origin (Caddy).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:9000",
        changeOrigin: true,
      },
    },
  },
});
