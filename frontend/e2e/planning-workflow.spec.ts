import { test, expect } from '@playwright/test'
import { readFileSync } from 'node:fs'

test('creates, tracks, revises, and persists an event plan', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: 'Plan your celebration' }).click()
  await expect(page.locator('.ai-indicator')).toHaveText('Demo mode')
  await expect(page.locator('.form-actions')).toContainText('Demo mode is active.')
  await page.getByLabel(/Describe your event/).fill(
    'A warm anniversary evening with gentle music and vegetarian food for friends and family.',
  )
  await page.getByLabel(/Celebration type/).selectOption('Anniversary')
  await page.getByLabel(/Location/).fill('Mysuru')
  await page.locator('input[type="number"]').nth(0).fill('45')
  await page.locator('input[type="number"]').nth(1).fill('25000')
  await page.getByLabel(/Food & dietary needs/).fill('Vegetarian')
  await page.getByRole('button', { name: /Create my plan/ }).click()

  await expect(page.getByRole('heading', { name: 'Anniversary.' })).toBeVisible()
  await expect(page.locator('.demo-banner')).toContainText('Demo-generated plan')
  await expect(page.locator('.clarification-box')).toContainText('What date do you have in mind?')
  await expect(page.locator('.timeline-notice')).toContainText('Add an event date')

  const firstTask = page.locator('.task-row').first()
  await firstTask.click()
  await expect(firstTask.locator('input')).toBeChecked()

  const firstVendor = page.locator('.vendor-fields').first()
  await firstVendor.locator('input').nth(0).fill('Garden venue candidate')
  await firstVendor.locator('input').nth(1).fill('planner@example.test')
  await firstVendor.locator('input').nth(2).fill('12500')
  await firstVendor.locator('select').selectOption('quoted')
  await firstVendor.getByRole('button', { name: 'Save details' }).click()
  await expect(page.getByText('Vendor details saved.')).toBeVisible()

  await page.locator('.actual-input input').first().fill('8000')
  await page.locator('.actual-input button').first().click()
  await expect(page.locator('.stat-card').nth(2)).toContainText('₹8,000')

  await page.locator('#revision').fill('Reduce the budget to ₹20,000')
  await page.getByRole('button', { name: /Refine this plan/ }).click()
  await expect(page.getByText('Revision applied and saved.')).toBeVisible()
  await expect(page.locator('.stat-card').nth(0)).toContainText('₹20,000')

  const downloadPromise = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Export plan' }).click()
  const download = await downloadPromise
  expect(download.suggestedFilename()).toMatch(/^festiva-anniversary.*\.json$/)
  const downloadPath = await download.path()
  expect(downloadPath).toBeTruthy()
  const exported = JSON.parse(readFileSync(downloadPath!, 'utf8'))
  expect(exported.event.budget).toBe(20000)
  expect(exported.actual_total).toBe(8000)

  const response = await page.request.get('http://127.0.0.1:8000/api/plans')
  expect(response.ok()).toBeTruthy()
  const [saved] = await response.json()
  expect(saved.event.budget).toBe(20000)
  expect(saved.actual_total).toBe(8000)
  expect(saved.prep_tasks[0].completed).toBe(true)
  expect(saved.vendors[0]).toMatchObject({
    vendor_name: 'Garden venue candidate',
    contact: 'planner@example.test',
    quotation: 12500,
    status: 'quoted',
  })
})
