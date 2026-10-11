import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In dev, /api/* goes to the FastAPI server (uvicorn on :8000). In Docker, nginx does the same.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": {
        target: process.env.API_URL ?? "http://localhost:8000",
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
