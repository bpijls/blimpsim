import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// `api` is the Docker service name — the dev server runs inside the network.
export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 3000,
    // Vite rejects requests for hostnames it does not know; Caddy forwards APP_DOMAIN.
    allowedHosts: [process.env.APP_DOMAIN].filter(Boolean),
    // ws: the telemetry stream is a WebSocket under /api.
    proxy: { "/api": { target: "http://api:8000", changeOrigin: true, ws: true } },
  },
  // Two pages: the monitor and the stand-alone remote control.
  build: { rollupOptions: { input: ["index.html", "remote.html"] } },
  test: { environment: "jsdom", globals: true },
});
