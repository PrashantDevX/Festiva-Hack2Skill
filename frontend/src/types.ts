export type EventInput = {
  description: string
  event_type: string
  event_date: string | null
  location: string
  guest_count: number
  budget: number
  currency: string
  preferences: string
  dietary_needs: string
  special_requirements: string
}

export type Expense = {
  id: string
  category: string
  item: string
  estimated_amount: number
  actual_amount: number | null
  status: 'estimated' | 'quoted' | 'confirmed'
  note: string
}

export type PrepTask = {
  id: string
  title: string
  deadline: string | null
  priority: 'high' | 'medium' | 'low'
  completed: boolean
}

export type Vendor = {
  id: string
  category: string
  requirement: string
  vendor_name: string
  contact: string
  quotation: number | null
  status: 'to_research' | 'contacted' | 'quoted' | 'booked'
  completed: boolean
  notes: string
}

export type ScheduleItem = {
  time: string
  title: string
  detail: string
}

export type Idea = {
  title: string
  description: string
  rationale: string
  estimated_impact: string
}

export type Plan = {
  id: string
  created_at: string
  updated_at: string
  event: EventInput
  overview: string
  clarifying_questions: string[]
  theme_options: string[]
  expenses: Expense[]
  prep_tasks: PrepTask[]
  schedule: ScheduleItem[]
  vendors: Vendor[]
  ideas: Idea[]
  savings: string[]
  assumptions: string[]
  estimated_total: number
  actual_total: number
  remaining_budget: number
  over_budget: boolean
  timeline_notice: string | null
  ai_mode: 'demo' | 'live'
}

export type Health = {
  status: 'ok' | 'degraded'
  ai_mode: 'demo' | 'live' | 'invalid'
  provider_configured: boolean
}

/** Editable fields accepted by the vendor PATCH endpoint. */
export type VendorUpdate = Partial<
  Pick<Vendor, 'completed' | 'vendor_name' | 'contact' | 'quotation' | 'status' | 'notes'>
>

/** Editable fields accepted by the expense PATCH endpoint. */
export type ExpenseUpdate = Partial<Pick<Expense, 'actual_amount' | 'status'>>

/** Local form state for a vendor row; quotation stays a string while editing. */
export type VendorDraft = {
  vendor_name: string
  contact: string
  quotation: string
  status: Vendor['status']
  notes: string
}
