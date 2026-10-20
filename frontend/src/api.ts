import type { EventInput, Health, Plan, Vendor } from './types'

export class ApiError extends Error {
  readonly status: number
  readonly category: string | null
  readonly retryAfter: number | null

  constructor(
    message: string,
    status = 0,
    category: string | null = null,
    retryAfter: number | null = null,
  ) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.category = category
    this.retryAfter = retryAfter
  }
}

// Exceeds the server's worst realistic path: three 45s attempts plus backoff.
const REQUEST_TIMEOUT_MS = 150_000

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const controller = new AbortController()
  const timer = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS)
  let response: Response
  try {
    response = await fetch(path, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...init?.headers },
      signal: init?.signal ?? controller.signal,
    })
  } catch (reason) {
    if (reason instanceof DOMException && reason.name === 'AbortError') {
      throw new ApiError(
        'The planning service took too long to respond. The request may still finish on the server; check Saved events before retrying.',
        0,
        'timeout',
      )
    }
    throw new ApiError(
      'Cannot reach the planning service. Check that the backend is running and retry.',
      0,
      'network',
    )
  } finally {
    window.clearTimeout(timer)
  }

  if (!response.ok) {
    const payload = (await response.json().catch(() => ({}))) as {
      detail?: string
      category?: string
    }
    const header = response.headers.get('Retry-After')
    const retryAfter =
      header !== null && Number.isFinite(Number(header)) ? Number(header) : null
    const base = payload.detail ?? `Request failed (${response.status}). Please retry.`
    const message =
      response.status === 429 && retryAfter !== null
        ? `${base} Retry in about ${retryAfter} seconds.`
        : base
    throw new ApiError(message, response.status, payload.category ?? null, retryAfter)
  }

  return (await response.json()) as T
}

export const api = {
  health: () => request<Health>('/api/health'),
  listPlans: () => request<Plan[]>('/api/plans'),
  createPlan: (event: EventInput) =>
    request<Plan>('/api/plans', { method: 'POST', body: JSON.stringify(event) }),
  getPlan: (id: string) => request<Plan>(`/api/plans/${id}`),
  revise: (id: string, instructions: string) =>
    request<Plan>(`/api/plans/${id}/revise`, {
      method: 'POST',
      body: JSON.stringify({ instructions }),
    }),
  updateTask: (planId: string, taskId: string, completed: boolean) =>
    request<Plan>(`/api/plans/${planId}/tasks/${taskId}`, {
      method: 'PATCH',
      body: JSON.stringify({ completed }),
    }),
  updateVendor: (planId: string, vendorId: string, changes: Partial<Vendor>) =>
    request<Plan>(`/api/plans/${planId}/vendors/${vendorId}`, {
      method: 'PATCH',
      body: JSON.stringify(changes),
    }),
  updateExpense: (
    planId: string,
    expenseId: string,
    changes: { actual_amount?: number | null; status?: 'estimated' | 'quoted' | 'confirmed' },
  ) =>
    request<Plan>(`/api/plans/${planId}/expenses/${expenseId}`, {
      method: 'PATCH',
      body: JSON.stringify(changes),
    }),
}
