import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vite";

// Dev: `npm run dev` proxies /api to the FastAPI server on :8000.
// Build: `npm run build` writes dist/, which the server serves at /.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { proxy: { "/api": "http://127.0.0.1:8000" } },
  build: { outDir: "dist" },
});
