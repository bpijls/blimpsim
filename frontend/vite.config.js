import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// `api` is the Docker service name — the dev server runs inside the network.
export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 3000,
    proxy: { "/api": { target: "http://api:8000", changeOrigin: true } },
  },
  test: { environment: "jsdom", globals: true },
});
