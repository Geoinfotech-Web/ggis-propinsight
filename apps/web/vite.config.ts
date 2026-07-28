import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: Number(process.env.PORT) || 5173,
    proxy: {
      // Proxy API calls to the FastAPI gateway during development.
      // Host 8001 avoids the GGIS Flood Watch stack on 8000.
      "/v1": "http://localhost:8001",
      "/health": "http://localhost:8001",
    },
  },
});
