import { test, expect, type Page } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'

const WCAG_TAGS = [
  'wcag2a',
  'wcag2aa',
  'wcag21a',
  'wcag21aa',
  'wcag22a',
  'wcag22aa',
]

async function audit(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(WCAG_TAGS).analyze()
  return results.violations
}

test('welcome and planning form pass automated WCAG 2.2 A/AA checks', async ({
  page,
}) => {
  await page.goto('/')

  const welcome = await audit(page)
  expect(welcome, JSON.stringify(welcome, null, 2)).toEqual([])

  await expect(
    page.getByRole('img', {
      name: 'Illustration of a celebration invitation and flowers',
    }),
  ).toBeVisible()
  const brand = page.getByRole('link', { name: 'Festiva AI workspace' })
  await expect(brand).toHaveAttribute('href', '#main-content')
  await expect(page.locator('#main-content')).toHaveCount(1)

  await page.keyboard.press('Tab')
  await expect(page.locator('.skip-link')).toBeFocused()
  await page.keyboard.press('Enter')
  await expect(page.locator('#main-content')).toBeFocused()

  await page.getByRole('button', { name: 'Plan your celebration' }).click()
  await expect(page.locator('#main-content')).toBeFocused()
  await expect(page.getByRole('spinbutton', { name: /Total budget/ })).toBeVisible()
  const form = await audit(page)
  expect(form, JSON.stringify(form, null, 2)).toEqual([])

  for (const width of [375, 768, 1280]) {
    await page.setViewportSize({ width, height: 900 })
    const overflows = await page.evaluate(
      () => document.documentElement.scrollWidth > window.innerWidth + 1,
    )
    expect(overflows, `horizontal overflow at ${width}px`).toBe(false)
  }
})

test('generated plan view passes automated WCAG 2.2 A/AA checks', async ({
  page,
}) => {
  await page.goto('/')
  await page.getByRole('button', { name: 'Plan your celebration' }).click()
  await page.getByLabel(/Describe your event/).fill(
    'A calm garden birthday with local vegetarian food, acoustic music, and family-friendly activities.',
  )
  await page.getByLabel(/Location/).fill('Pune')
  await page.locator('input[type="number"]').nth(0).fill('30')
  await page.locator('input[type="number"]').nth(1).fill('15000')
  await page.getByLabel(/Food & dietary needs/).fill('Vegetarian')
  await page.getByRole('button', { name: /Create my plan/ }).click()

  await expect(page.getByRole('heading', { name: 'Birthday.' })).toBeVisible()
  await expect(page.locator('#main-content')).toBeFocused()
  const firstExpenseItem = await page.locator('.expense-title span').first().innerText()
  await expect(page.locator('.actual-input input').first()).toHaveAccessibleName(
    `Actual spending for ${firstExpenseItem}`,
  )
  const plan = await audit(page)
  expect(plan, JSON.stringify(plan, null, 2)).toEqual([])
})
