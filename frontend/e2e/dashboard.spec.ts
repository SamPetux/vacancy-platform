import { expect, test } from '@playwright/test'

test('admin dashboard shows NN feed queue', async ({ page }) => {
  await page.goto('http://127.0.0.1:5173/')
  await expect(page.getByRole('heading', { name: /Нижний Новгород/i })).toBeVisible()
  await expect(page.getByTestId('api-status')).toContainText(/OK/i, { timeout: 15000 })
  await expect(page.getByTestId('collection-stats')).toBeVisible()
  await expect(page.getByTestId('feed-list')).toContainText(/VQS/i, { timeout: 15000 })
})
