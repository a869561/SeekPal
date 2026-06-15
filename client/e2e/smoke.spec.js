// E2E mínimo de SeekPal: cubre el flujo principal del usuario.
//
//   1. Login con contraseña → entra a la app (aterriza en /stats).
//   2. Búsqueda de un término → aparecen resultados.
//   3. Navegación a Ajustes vía la barra lateral.
//
// Selectores estructurales (type/role/href) en vez de textos i18n para no
// depender del idioma activo. Requiere backend en :3000 con datos indexados.

import { test, expect } from "@playwright/test";

const PASSWORD = "seekpal123";

// Inicia sesión antes de cada test. Tras el login la app redirige a /stats
// (ver client/src/pages/Login.jsx).
test.beforeEach(async ({ page }) => {
  await page.goto("/");
  const passwordInput = page.locator('input[type="password"]');
  // Esperamos a que el formulario de login aparezca (la redirección a /login es
  // client-side y puede tardar un instante). Si no aparece, ya estamos autenticados.
  try {
    await passwordInput.waitFor({ state: "visible", timeout: 5_000 });
    await passwordInput.fill(PASSWORD);
    await page.locator('button[type="submit"]').click();
  } catch {
    /* sin formulario de login → sesión ya iniciada */
  }
  // En cualquier caso, tras esto NO debemos seguir en /login.
  await expect(page).not.toHaveURL(/\/login/, { timeout: 15_000 });
});

test("login da acceso a la app (aterriza en /stats)", async ({ page }) => {
  await expect(page).toHaveURL(/\/stats/);
});

test("una búsqueda devuelve resultados", async ({ page }) => {
  await page.goto("/search");
  const box = page.getByRole("textbox").first();
  await box.fill("valorant");
  await box.press("Enter");
  // La búsqueda en CPU tarda ~20 s; esperamos a que aparezca al menos un
  // resultado con un nombre de fichero conocido del corpus de prueba.
  await expect(
    page.getByText(/\.(png|jpe?g|md|pdf|docx|txt|mp4|wav)/i).first()
  ).toBeVisible({ timeout: 45_000 });
});

test("se puede navegar a Ajustes", async ({ page }) => {
  await page.locator('a[href$="/settings"]').first().click();
  await expect(page).toHaveURL(/\/settings/);
});
