import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  fullyParallel: false,
  workers: 1,
  timeout: 30_000,
  expect: { timeout: 5_000 },
  outputDir: "../data/private/phase5-browser-results",
  reporter: "list",
  use: {
    baseURL: "http://127.0.0.1:3210",
    channel: process.platform === "win32" ? "msedge" : undefined,
    viewport: { width: 1440, height: 900 },
    trace: "retain-on-failure",
  },
  webServer: {
    command: "node node_modules/next/dist/bin/next dev --hostname 127.0.0.1 --port 3210",
    url: "http://127.0.0.1:3210",
    timeout: 120_000,
    reuseExistingServer: false,
  },
});
