import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In development the Vite server proxies API calls to FastAPI, so the browser sees a single origin (no CORS needed).
const API = process.env.VITE_API_TARGET ?? "http://127.0.0.1:8000";
const prefixes = "auth|me|status|dashboard|groups|users|documents|jobs|query|graph|audit|health|docs|openapi.json";

export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy: { [`^/(${prefixes})(/|$)`]: { target: API, changeOrigin: false } } },
  build: { outDir: "dist", sourcemap: false, chunkSizeWarningLimit: 700 },
});
