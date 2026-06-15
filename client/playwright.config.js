// Configuración de Playwright para el testing E2E del frontend de SeekPal.
//
// Ejecuta contra el Google Chrome instalado en el equipo (channel: "chrome"),
// no contra una build de Chromium descargada — así no añade peso y prueba el
// navegador real del usuario.
//
// Requisitos para correr los tests:
//   1. El backend debe estar arrancado (http://localhost:3000) con datos indexados.
//   2. El dev server de Vite se arranca automáticamente (webServer) si no lo está.
//
// Uso: `npm run test:e2e`  (o `npx playwright test`)

import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  // La búsqueda usa reranker en CPU (~20 s); damos margen amplio por test.
  timeout: 60_000,
  expect: { timeout: 30_000 },
  fullyParallel: false,
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: "http://localhost:5173",
    channel: "chrome", // usa el Google Chrome instalado
    headless: true,
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "chrome",
      use: { ...devices["Desktop Chrome"], channel: "chrome" },
    },
  ],
  webServer: {
    command: "npm run dev",
    url: "http://localhost:5173",
    reuseExistingServer: true,
    timeout: 120_000,
  },
});
