import { defineConfig } from "@playwright/test";

const editorURL = process.env.EDITOR_URL ?? "http://127.0.0.1:8765";

export default defineConfig({
  testDir: "tests/browser",
  fullyParallel: false,
  workers: 1,
  use: {
    baseURL: editorURL,
    channel: process.env.EDITOR_BROWSER_CHANNEL ?? (process.platform === "win32" ? "msedge" : undefined),
    viewport: { width: 1550, height: 980 },
    headless: true,
    screenshot: "only-on-failure",
  },
});
