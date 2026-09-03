import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, ".", "");
  return {
    plugins: [react()],
    server: {
      port: 5173,
      proxy: {
        "/api": {
          target: env.VITE_API_TARGET || "http://127.0.0.1:8000",
          changeOrigin: true
        }
      }
    },
    build: {
      sourcemap: false,
      chunkSizeWarningLimit: 800,
      rollupOptions: {
        output: {
          manualChunks(id) {
            if (id.indexOf("node_modules/@mui/") >= 0 || id.indexOf("node_modules/@emotion/") >= 0) {
              return "mui";
            }
            if (id.indexOf("node_modules/@tanstack/react-query") >= 0) return "query";
            return undefined;
          }
        }
      }
    }
  };
});
