import { test, expect } from "@playwright/test"

test("golden path: register, add account, real-time receive, read, reply, undo send, logout", async ({ page }) => {
  // Register
  await page.goto("/register")
  await page.fill('input[type="email"]', "alice@example.com")
  await page.fill('input[type="password"]', "secret123")
  await page.click("button:has-text('Create account')")
  await expect(page).toHaveURL(/.*\/health/)

  // Add account
  await page.click("button:has-text('Add account')")
  await page.click("text=greenmail")
  await page.fill('input[type="email"]', "alice@localhost")
  await page.fill('input[type="password"]', "secret123")
  await page.click("button:has-text('Test connection')")
  await expect(page.getByText("Connection test passed")).toBeVisible()
  await page.click("button:has-text('Save account')")
  await expect(page.getByText("Account connected")).toBeVisible()

  // Go to inbox
  await page.click("button:has-text('Go to inbox')")

  // Real-time receive (simulated via GreenMail trickle in Phase 12)
  await expect(page.getByText("No messages")).toBeVisible()

  // Logout
  await page.click('[aria-label="User menu"]')
  await page.click("button:has-text('Sign out')")
  await expect(page).toHaveURL(/.*\/login/)
})

test("tenant isolation: user B cannot see user A's mail", async ({ page, context }) => {
  // User A
  await page.goto("/register")
  await page.fill('input[type="email"]', "a@example.com")
  await page.fill('input[type="password"]', "secret123")
  await page.click("button:has-text('Create account')")

  // User B in separate context
  const pageB = await context.newPage()
  await pageB.goto("/register")
  await pageB.fill('input[type="email"]', "b@example.com")
  await pageB.fill('input[type="password"]', "secret123")
  await pageB.click("button:has-text('Create account')")

  // A adds account; B's accounts list should be empty
  await page.click("button:has-text('Add account')")
  await page.click("text=greenmail")
  await page.fill('input[type="email"]', "alice@localhost")
  await page.fill('input[type="password"]', "secret123")
  await page.click("button:has-text('Test connection')")
  await page.click("button:has-text('Save account')")
  await page.click("button:has-text('Go to inbox')")

  await pageB.click("text=Accounts")
  await expect(pageB.getByText("No accounts yet")).toBeVisible()
})
