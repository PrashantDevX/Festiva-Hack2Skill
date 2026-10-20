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
  schedule: { time: string; title: string; detail: string }[]
  vendors: Vendor[]
  ideas: { title: string; description: string; rationale: string; estimated_impact: string }[]
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
  status: string
  ai_mode: 'demo' | 'live' | 'invalid'
  provider: string
  model: string | null
  provider_configured: boolean
}
