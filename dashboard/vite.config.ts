/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  // `npm run dev` talks to a local `factory server` on its default port.
  server: { proxy: { "/api": "http://localhost:47821" } },
  test: { environment: "jsdom" },
});
