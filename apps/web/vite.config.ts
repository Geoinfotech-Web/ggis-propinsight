import path from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const rootDir = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(rootDir, "../..");

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@design": path.resolve(repoRoot, "design"),
    },
  },
  server: {
    // Stable port so the dev URL doesn't drift on restart. 5173 is taken by the
    // GGIS Flood Watch frontend on this host, so AIA uses 5174.
    port: Number(process.env.PORT) || 5174,
    strictPort: true,
    fs: {
      allow: [repoRoot],
    },
    proxy: {
      // Proxy API calls to the FastAPI gateway during development.
      // Host 8001 avoids the GGIS Flood Watch stack on 8000.
      "/v1": "http://localhost:8001",
      "/health": "http://localhost:8001",
      "/geocode": {
        target: "https://nominatim.openstreetmap.org",
        changeOrigin: true,
        rewrite: (path: string) => path.replace(/^\/geocode/, ""),
        headers: {
          "User-Agent": "PropInsight/0.1 (Geoinfotech GGIS; local-dev)",
        },
      },
    },
  },
});
