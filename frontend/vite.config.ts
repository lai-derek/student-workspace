import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// The built app goes inside the Python package, which serves it from 127.0.0.1.
// In development, run `student-workspace serve WS --port 8766 --dev-origin http://localhost:5173`
// and `npm run dev`; Vite forwards /api to that server.
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "../packages/student-workspace/src/student_workspace/web/static",
    emptyOutDir: true,
    chunkSizeWarningLimit: 2000,
  },
  server: {
    port: 5173,
    proxy: { "/api": "http://127.0.0.1:8766" },
  },
  test: {
    environment: "jsdom",
  },
});
