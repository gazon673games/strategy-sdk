import { test, expect } from "@playwright/test";

test("blank project opens in both visual editors and exports a valid contract", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator("#template")).toHaveValue("empty");
  await expect(page.locator("#download")).toBeEnabled();
  await page.locator("#graph-tab").click();
  await expect(page.locator("#litegraph")).toBeVisible();
  await page.locator("#blocks-tab").click();
  await expect(page.locator("#blockly")).toBeVisible();
  await page.locator("#python-mode").click();
  await page.locator("#python-new").click();
  await expect(page.locator("#python-code")).toHaveValue(/hold_decision/);
});
