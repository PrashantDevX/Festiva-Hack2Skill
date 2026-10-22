const currencyFormatters = new Map<string, Intl.NumberFormat>()

function currencyFormatter(currency: string): Intl.NumberFormat {
  const existing = currencyFormatters.get(currency)
  if (existing) return existing
  const formatter = new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency,
    maximumFractionDigits: 0,
  })
  currencyFormatters.set(currency, formatter)
  return formatter
}

export function formatMoney(amount: number, currency: string): string {
  return currencyFormatter(currency).format(amount)
}

const dateFormatter = new Intl.DateTimeFormat('en-IN', {
  dateStyle: 'medium',
  timeZone: 'UTC',
})

export function formatDate(value: string | null): string {
  return value ? dateFormatter.format(new Date(`${value}T00:00:00Z`)) : 'Date to be decided'
}

export function getErrorMessage(reason: unknown, fallback: string): string {
  return reason instanceof Error ? reason.message : fallback
}
