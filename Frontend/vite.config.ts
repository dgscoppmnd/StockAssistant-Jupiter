import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  base: "/",
  plugins: [react()],
  server: {
    proxy: {
      "/media": {
        target: process.env.API_PROXY_TARGET || "http://localhost:8000",
        changeOrigin: true,
      },
      "/api": {
        target: process.env.API_PROXY_TARGET || "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
  resolve: {
    alias: {
      events: "events/"
    }
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
    sourcemap: false
  }
});
