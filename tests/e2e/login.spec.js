import { expect, test } from "@playwright/test";

test("local email login reaches the dashboard", async ({ page }) => {
  await page.goto("/accounts/login/");

  await expect(page.getByRole("heading", { name: "Access Atlas" })).toBeVisible();

  await page.getByLabel("Email").fill("playwright@example.com");
  await page.getByLabel("Display name").fill("Playwright");
  await page.getByRole("button", { name: "Continue with email" }).click();

  await expect(page).toHaveURL("/");
  await expect(page.getByRole("link", { name: "Dashboard" })).toHaveAttribute(
    "aria-current",
    "page",
  );
});
