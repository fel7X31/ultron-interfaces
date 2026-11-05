import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  base: "/novo/",
  build: { outDir: "../web/novo", emptyOutDir: true },
  server: { proxy: { "/api": "http://localhost:8790" } },
});
