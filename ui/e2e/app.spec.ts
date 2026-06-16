import { expect, test } from "@playwright/test";

test("renders the dashboard without runtime errors", async ({ page }) => {
  const runtimeErrors: string[] = [];
  page.on("pageerror", (error) => runtimeErrors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error") {
      runtimeErrors.push(message.text());
    }
  });

  await page.goto("/");

  await expect(page.getByRole("heading", { name: "Agent runs" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Setup checks" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Launch plan" })).toBeVisible();
  await expect(page.getByText("Preview mode")).toBeVisible();
  expect(runtimeErrors).toEqual([]);
});
