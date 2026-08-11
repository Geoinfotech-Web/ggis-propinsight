import path from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { viteStaticCopy } from "vite-plugin-static-copy";

const rootDir = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(rootDir, "../..");
const cesiumSource = "node_modules/cesium/Build/Cesium";
const cesiumBaseUrl = "/cesiumStatic/";

// API target: localhost:8001 on the host, or the `api` service in compose.
const apiTarget = process.env.API_PROXY_TARGET || "http://localhost:8001";

export default defineConfig({
  plugins: [
    react(),
    viteStaticCopy({
      targets: [
        { src: `${cesiumSource}/Workers`, dest: "cesiumStatic" },
        { src: `${cesiumSource}/ThirdParty`, dest: "cesiumStatic" },
        { src: `${cesiumSource}/Assets`, dest: "cesiumStatic" },
        { src: `${cesiumSource}/Widgets`, dest: "cesiumStatic" },
      ],
    }),
  ],
  define: {
    CESIUM_BASE_URL: JSON.stringify(cesiumBaseUrl),
  },
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
    host: true, // bind 0.0.0.0 so the dev server is reachable from the container
    // Polling is needed for HMR when the source is a bind-mounted volume on
    // Docker Desktop / Windows (inotify events don't cross the boundary).
    watch: process.env.VITE_USE_POLLING ? { usePolling: true } : undefined,
    fs: {
      allow: [repoRoot],
    },
    proxy: {
      // Proxy API calls to the FastAPI gateway during development.
      // Host: localhost:8001 (avoids GGIS Flood Watch on 8000). Compose: api:8000.
      "/v1": apiTarget,
      "/health": apiTarget,
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
