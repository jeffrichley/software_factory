/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  // `npm run dev` talks to a local `factory server` on its default port.
  server: { proxy: { "/api": "http://localhost:47821" } },
  // CSS is processed only for the stylesheet the layout guards read (layout.test.ts); elsewhere it is stubbed.
  test: { environment: "jsdom", css: { include: [/components\.css/] } },
});
