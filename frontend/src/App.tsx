import { useEffect, useMemo, useRef, useState, type FormEvent } from 'react'
import {
  ArrowDownToLine,
  ArrowRight,
  CalendarDays,
  Check,
  ChevronDown,
  CircleCheck,
  ClipboardCheck,
  Coins,
  Flower2,
  Heart,
  LoaderCircle,
  MapPin,
  Plus,
  Sparkles,
  WandSparkles,
} from 'lucide-react'
import { api } from './api'
import type { EventInput, Expense, Health, Plan, Vendor } from './types'

type VendorDraft = {
  vendor_name: string
  contact: string
  quotation: string
  status: Vendor['status']
  notes: string
}

const initialEvent: EventInput = {
  description: '',
  event_type: 'Birthday',
  event_date: '',
  location: '',
  guest_count: 50,
  budget: 40000,
  currency: 'INR',
  preferences: '',
  dietary_needs: '',
  special_requirements: '',
}

const money = (amount: number, currency: string) =>
  new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency,
    maximumFractionDigits: 0,
  }).format(amount)

const dateLabel = (value: string | null) =>
  value
    ? new Intl.DateTimeFormat('en-IN', { dateStyle: 'medium', timeZone: 'UTC' }).format(
        new Date(`${value}T00:00:00Z`),
      )
    : 'Date to be decided'

function App() {
  const [plans, setPlans] = useState<Plan[]>([])
  const [plan, setPlan] = useState<Plan | null>(null)
  const [health, setHealth] = useState<Health | null>(null)
  const [event, setEvent] = useState<EventInput>(initialEvent)
  const [showCreate, setShowCreate] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [revision, setRevision] = useState('')
  const [revisionLoading, setRevisionLoading] = useState(false)
  const [expenseDrafts, setExpenseDrafts] = useState<Record<string, string>>({})
  const [vendorDrafts, setVendorDrafts] = useState<Record<string, VendorDraft>>({})
  const pendingRef = useRef<Set<string>>(new Set())
  const [pendingKeys, setPendingKeys] = useState<Set<string>>(new Set())

  const beginRequest = (key: string) => {
    if (pendingRef.current.has(key)) return false
    pendingRef.current.add(key)
    setPendingKeys(new Set(pendingRef.current))
    return true
  }

  const endRequest = (key: string) => {
    pendingRef.current.delete(key)
    setPendingKeys(new Set(pendingRef.current))
  }

  const isPending = (key: string) => pendingKeys.has(key)

  const refreshPlans = async (selected?: string) => {
    const saved = await api.listPlans()
    setPlans(saved)
    const next = selected ? saved.find((item) => item.id === selected) : undefined
    if (next) setPlan(next)
    return saved
  }

  const refreshQuietly = async (selected?: string) => {
    try {
      await refreshPlans(selected)
    } catch {
      setError(
        'Your changes are saved, but the saved-events list could not refresh. Reload the page to update it.',
      )
    }
  }

  useEffect(() => {
    Promise.all([api.health(), api.listPlans()])
      .then(([service, saved]) => {
        setHealth(service)
        setPlans(saved)
        if (saved.length) setPlan(saved[0])
      })
      .catch((reason: Error) => setError(reason.message))
  }, [])

  const completion = useMemo(() => {
    if (!plan || !plan.prep_tasks.length) return 0
    return Math.round(
      (plan.prep_tasks.filter((task) => task.completed).length / plan.prep_tasks.length) * 100,
    )
  }, [plan])

  const updateEvent = (field: keyof EventInput, value: string | number | null) =>
    setEvent((current) => ({ ...current, [field]: value }))

  const createPlan = async (submitEvent: FormEvent<HTMLFormElement>) => {
    submitEvent.preventDefault()
    if (!beginRequest('create')) return
    setError('')
    setNotice('')
    setLoading(true)
    try {
      const saved = await api.createPlan({ ...event, event_date: event.event_date || null })
      setPlan(saved)
      setEvent(saved.event)
      setShowCreate(false)
      await refreshQuietly(saved.id)
      setNotice(saved.ai_mode === 'demo' ? 'Demo plan saved. No live AI provider was used.' : 'Your new plan is ready and saved.')
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Could not generate your plan.')
    } finally {
      endRequest('create')
      setLoading(false)
    }
  }

  const revisePlan = async (submitEvent: FormEvent<HTMLFormElement>) => {
    submitEvent.preventDefault()
    if (!plan || !revision.trim() || !beginRequest('revise')) return
    setError('')
    setNotice('')
    setRevisionLoading(true)
    try {
      const updated = await api.revise(plan.id, revision.trim())
      setPlan(updated)
      setEvent(updated.event)
      setRevision('')
      await refreshQuietly(updated.id)
      setNotice('Revision applied and saved.')
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'The revision could not be applied.')
    } finally {
      endRequest('revise')
      setRevisionLoading(false)
    }
  }

  const handleToggle = async (
    kind: 'task' | 'vendor',
    id: string,
    completed: boolean,
  ) => {
    const key = `${kind}:${id}`
    if (!plan || !beginRequest(key)) return
    setError('')
    try {
      const updated =
        kind === 'task'
          ? await api.updateTask(plan.id, id, completed)
          : await api.updateVendor(plan.id, id, { completed })
      setPlan(updated)
      await refreshQuietly(updated.id)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Could not save this checklist update.')
    } finally {
      endRequest(key)
    }
  }

  const saveActual = async (expenseId: string) => {
    if (!plan) return
    const value = expenseDrafts[expenseId]?.trim() ?? ''
    const amount = value === '' ? null : Number(value)
    if (amount !== null && (!Number.isFinite(amount) || amount < 0)) {
      setError('Enter a non-negative actual amount or leave it blank.')
      return
    }
    if (!beginRequest(`expense:${expenseId}`)) return
    setError('')
    try {
      const updated = await api.updateExpense(plan.id, expenseId, { actual_amount: amount })
      setPlan(updated)
      setExpenseDrafts((current) => {
        const copy = { ...current }
        delete copy[expenseId]
        return copy
      })
      await refreshQuietly(updated.id)
      setNotice('Actual spending saved.')
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Could not save actual spending.')
    } finally {
      endRequest(`expense:${expenseId}`)
    }
  }

  const saveExpenseStatus = async (
    expenseId: string,
    status: 'estimated' | 'quoted' | 'confirmed',
  ) => {
    if (!plan || !beginRequest(`status:${expenseId}`)) return
    setError('')
    try {
      const updated = await api.updateExpense(plan.id, expenseId, { status })
      setPlan(updated)
      await refreshQuietly(updated.id)
      setNotice('Quotation status saved.')
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Could not update quotation status.')
    } finally {
      endRequest(`status:${expenseId}`)
    }
  }

  const vendorDraft = (vendor: Vendor): VendorDraft =>
    vendorDrafts[vendor.id] ?? {
      vendor_name: vendor.vendor_name,
      contact: vendor.contact,
      quotation: vendor.quotation === null ? '' : String(vendor.quotation),
      status: vendor.status,
      notes: vendor.notes,
    }

  const updateVendorDraft = <Key extends keyof VendorDraft>(
    vendor: Vendor,
    field: Key,
    value: VendorDraft[Key],
  ) => {
    setVendorDrafts((current) => ({
      ...current,
      [vendor.id]: { ...vendorDraft(vendor), [field]: value },
    }))
  }

  const saveVendor = async (vendor: Vendor) => {
    if (!plan) return
    const draft = vendorDraft(vendor)
    const quotation = draft.quotation.trim() === '' ? null : Number(draft.quotation)
    if (quotation !== null && (!Number.isFinite(quotation) || quotation < 0)) {
      setError('Enter a non-negative vendor quotation or leave it blank.')
      return
    }
    if (!beginRequest(`vendor:${vendor.id}`)) return
    setError('')
    try {
      const updated = await api.updateVendor(plan.id, vendor.id, {
        vendor_name: draft.vendor_name,
        contact: draft.contact,
        quotation,
        status: draft.status,
        notes: draft.notes,
      })
      setPlan(updated)
      setVendorDrafts((current) => {
        const copy = { ...current }
        delete copy[vendor.id]
        return copy
      })
      await refreshQuietly(updated.id)
      setNotice('Vendor details saved.')
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Could not save vendor details.')
    } finally {
      endRequest(`vendor:${vendor.id}`)
    }
  }

  const selectPlan = async (id: string) => {
    if (!beginRequest('select-plan')) return
    setError('')
    try {
      const selected = await api.getPlan(id)
      setPlan(selected)
      setEvent(selected.event)
      setShowCreate(false)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Could not open this saved plan.')
    } finally {
      endRequest('select-plan')
    }
  }

  const exportPlan = () => {
    if (!plan) return
    const blob = new Blob([JSON.stringify(plan, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `festiva-${plan.event.event_type.toLowerCase().replace(/\s+/g, '-')}.json`
    anchor.click()
    window.setTimeout(() => URL.revokeObjectURL(url), 1000)
  }

  const startNewPlan = () => {
    setEvent(initialEvent)
    setShowCreate(true)
    setError('')
    setNotice('')
  }

  const showError = (message: string) => <p className="alert error" role="alert">{message}</p>

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">Skip to main content</a>
      <aside className="sidebar">
        <a className="brand" href="#home" aria-label="Festiva AI home">
          <span className="brand-mark"><Flower2 size={21} strokeWidth={1.8} /></span>
          <span>festiva<span className="brand-ai">.ai</span></span>
        </a>
        <p className="side-label">YOUR PLANNER</p>
        <button className={`side-link ${!showCreate ? 'active' : ''}`} onClick={() => setShowCreate(false)}>
          <Sparkles size={17} /> Workspace
        </button>
        <button className="side-link" onClick={startNewPlan}>
          <Plus size={17} /> Plan an event
        </button>
        <div className="saved-heading">
          <p className="side-label">SAVED EVENTS</p>
          <span className="saved-count">{plans.length}</span>
        </div>
        <nav className="saved-list" aria-label="Saved events">
          {plans.length === 0 ? (
            <p className="empty-side">Your plans will live here.</p>
          ) : plans.map((saved) => (
            <button
              className={`saved-event ${plan?.id === saved.id && !showCreate ? 'selected' : ''}`}
              key={saved.id}
              aria-current={plan?.id === saved.id && !showCreate ? 'page' : undefined}
              onClick={() => void selectPlan(saved.id)}
            >
              <span className="event-dot" aria-hidden="true" />
              <span className="saved-event-text">
                <strong>{saved.event.event_type}</strong>
                <small>{saved.event.location}</small>
              </span>
              <ChevronDown size={14} className="saved-chevron" aria-hidden="true" />
            </button>
          ))}
        </nav>
        <div className="sidebar-footer">
          <span className="avatar">F</span>
          <span><strong>Your space</strong><small>Private on this device</small></span>
        </div>
      </aside>

      <main className="main-area" id="main-content" tabIndex={-1}>
        <header className="topbar">
          <div className="breadcrumb">Your workspace <span>/</span> {showCreate ? 'New event' : plan?.event.event_type ?? 'Overview'}</div>
          <div
            className={`ai-indicator ${health?.ai_mode === 'live' && health.provider_configured ? 'live' : ''}`}
            title={health?.model ? `Provider: ${health.provider}; model: ${health.model}` : undefined}
          >
            <span className="status-dot" />
            {health === null
              ? 'Checking AI status'
              : health.ai_mode === 'demo'
                ? 'Demo mode'
                : health.ai_mode === 'invalid'
                  ? 'AI configuration error'
                  : health.provider_configured
                    ? `Gemini · ${health.model ?? 'configured'}`
                    : 'Gemini needs setup'}
          </div>
        </header>

        <div className="content-wrap">
          <div className="sr-only" role="status" aria-live="polite">
            {loading ? 'Building your plan.' : revisionLoading ? 'Updating your plan.' : ''}
          </div>
          {error && showError(error)}
          {notice && <p className="alert success" role="status"><CircleCheck size={17} /> {notice}</p>}

          {showCreate ? (
            <section className="create-page">
              <button className="back-link" onClick={() => setShowCreate(false)}>← Back to workspace</button>
              <div className="page-title-row">
                <div>
                  <p className="eyebrow">LET'S MAKE IT MEANINGFUL</p>
                  <h1>Tell us what you're celebrating.</h1>
                  <p className="subtitle">A few details help shape a plan that feels like yours.</p>
                </div>
                <div className="title-icon"><Sparkles size={25} /></div>
              </div>
              <form className="event-form card" onSubmit={createPlan} aria-busy={loading}>
                <div className="form-section-heading"><span>01</span><div><h2>The occasion</h2><p>Start with the details you already know.</p></div></div>
                <label className="field full">
                  <span>Describe your event <b>*</b></span>
                  <textarea
                    required
                    minLength={10}
                    maxLength={4000}
                    value={event.description}
                    onChange={(e) => updateEvent('description', e.target.value)}
                    placeholder="A relaxed birthday dinner for my parents, with a garden setting and close family..."
                    rows={3}
                  />
                  <small>Include any details that matter to you. Don't include sensitive personal information.</small>
                </label>
                <div className="form-grid">
                  <label className="field">
                    <span>Celebration type <b>*</b></span>
                    <select value={event.event_type} onChange={(e) => updateEvent('event_type', e.target.value)}>
                      {['Wedding', 'Birthday', 'Anniversary', 'College event', 'Community celebration', 'Other'].map((item) => <option key={item}>{item}</option>)}
                    </select>
                  </label>
                  <label className="field">
                    <span>Event date</span>
                    <input type="date" value={event.event_date ?? ''} onChange={(e) => updateEvent('event_date', e.target.value || null)} />
                    <small>Leave blank if undecided; deadlines will be added once known.</small>
                  </label>
                  <label className="field">
                    <span>Location <b>*</b></span>
                    <input required minLength={2} maxLength={160} value={event.location} onChange={(e) => updateEvent('location', e.target.value)} placeholder="City or venue area" />
                  </label>
                  <label className="field">
                    <span>Guest count <b>*</b></span>
                    <input required type="number" min="1" max="100000" value={event.guest_count} onChange={(e) => updateEvent('guest_count', Number(e.target.value))} />
                  </label>
                </div>
                <div className="form-section-heading budget-heading"><span>02</span><div><h2>Make it work for you</h2><p>Budgets are estimates until you confirm real quotations.</p></div></div>
                <div className="form-grid">
                  <label className="field">
                    <span>Total budget <b>*</b></span>
                    <div className="input-combo">
                      <select aria-label="Currency" value={event.currency} onChange={(e) => updateEvent('currency', e.target.value)}>
                        <option value="INR">INR ₹</option><option value="USD">USD $</option><option value="EUR">EUR €</option><option value="GBP">GBP £</option>
                      </select>
                      <input required type="number" min="1" step="1" max="100000000" value={event.budget} onChange={(e) => updateEvent('budget', Number(e.target.value))} />
                    </div>
                  </label>
                  <label className="field">
                    <span>Food & dietary needs</span>
                    <input maxLength={500} value={event.dietary_needs} onChange={(e) => updateEvent('dietary_needs', e.target.value)} placeholder="e.g. vegetarian, nut-free options" />
                  </label>
                  <label className="field full">
                    <span>Your style & preferences</span>
                    <textarea rows={2} maxLength={1500} value={event.preferences} onChange={(e) => updateEvent('preferences', e.target.value)} placeholder="Themes, colors, cultural preferences, atmosphere..." />
                  </label>
                  <label className="field full">
                    <span>Special requirements</span>
                    <textarea rows={2} maxLength={1000} value={event.special_requirements} onChange={(e) => updateEvent('special_requirements', e.target.value)} placeholder="Accessibility, timing, or other constraints" />
                  </label>
                </div>
                <div className="form-actions">
                  <p><Sparkles size={16} /> {health?.ai_mode === 'invalid' ? 'The server AI configuration is invalid. Ask the operator to set demo or live mode.' : health?.ai_mode === 'live' && health.provider_configured ? `Gemini (${health.model ?? 'configured model'}) will create a structured plan on the server.` : health?.ai_mode === 'live' ? 'Live mode needs a valid server-side Gemini key and model before a plan can be created.' : 'Demo mode is active. This plan is generated locally, not by Gemini.'}</p>
                  <button className="primary-button" type="submit" disabled={loading}>
                    {loading ? <><LoaderCircle className="spin" size={17} /> Building your plan</> : <>Create my plan <ArrowRight size={17} /></>}
                  </button>
                </div>
              </form>
            </section>
          ) : plan ? (
            <section className="workspace">
              <div className="page-title-row workspace-title">
                <div>
                  <p className="eyebrow">A LITTLE MORE JOY, A LOT LESS GUESSWORK</p>
                  <h1>{plan.event.event_type}<span className="title-period">.</span></h1>
                  <div className="event-meta">
                    <span><CalendarDays size={15} /> {dateLabel(plan.event.event_date)}</span>
                    <span><MapPin size={15} /> {plan.event.location}</span>
                    <span><Heart size={15} /> {plan.event.guest_count} guests</span>
                  </div>
                </div>
                <div className="title-actions">
                  <button className="secondary-button" onClick={exportPlan}><ArrowDownToLine size={16} /> Export plan</button>
                  <button className="primary-button compact" onClick={startNewPlan}><Plus size={17} /> New event</button>
                </div>
              </div>

              {plan.ai_mode === 'demo' && (
                <div className="demo-banner"><Sparkles size={17} /><span><strong>Demo-generated plan</strong> — local planning logic was used. Add a Gemini API key on the server for live GenAI. Estimates are not vendor quotes.</span></div>
              )}

              <div className="stats-grid">
                <article className="stat-card budget-stat">
                  <div className="stat-top"><span>Total budget</span><span className="stat-icon"><Coins size={17} /></span></div>
                  <strong>{money(plan.event.budget, plan.event.currency)}</strong>
                  <small>{plan.event.guest_count} guests · planning limit</small>
                </article>
                <article className="stat-card">
                  <div className="stat-top"><span>Estimated spend</span><span className="stat-icon"><Flower2 size={17} /></span></div>
                  <strong>{money(plan.estimated_total, plan.event.currency)}</strong>
                  <small>{plan.over_budget ? 'Over budget — review estimates and actuals' : `${money(plan.remaining_budget, plan.event.currency)} estimated remaining`}</small>
                </article>
                <article className="stat-card">
                  <div className="stat-top"><span>Actual spend</span><span className="stat-icon"><Coins size={17} /></span></div>
                  <strong>{money(plan.actual_total, plan.event.currency)}</strong>
                  <small>Update as real costs come in</small>
                </article>
                <article className="stat-card progress-stat">
                  <div className="stat-top"><span>Planning progress</span><span className="stat-icon"><ClipboardCheck size={17} /></span></div>
                  <strong>{completion}%</strong>
                  <div className="progress-track" role="progressbar" aria-label="Preparation tasks complete" aria-valuenow={completion} aria-valuemin={0} aria-valuemax={100}><span style={{ width: `${completion}%` }} /></div>
                  <small>{plan.prep_tasks.filter((task) => task.completed).length} of {plan.prep_tasks.length} tasks done</small>
                </article>
              </div>

              <div className="two-column">
                <div className="main-column">
                  <article className="card overview-card">
                    <div className="section-heading"><div><p className="eyebrow">YOUR CELEBRATION AT A GLANCE</p><h2>A thoughtful starting point</h2></div><span className="soft-icon"><WandSparkles size={20} /></span></div>
                    <p className="overview-copy">{plan.overview}</p>
                    {plan.clarifying_questions.length > 0 && (
                      <div className="clarification-box">
                        <strong>A detail to confirm</strong>
                        <ul>{plan.clarifying_questions.map((question) => <li key={question}>{question}</li>)}</ul>
                      </div>
                    )}
                    <div className="theme-chips">{plan.theme_options.map((theme) => <span key={theme}>{theme}</span>)}</div>
                    <div className="ai-checks">
                      <span><Check size={14} /> Plan {plan.ai_mode === 'live' ? 'generated with Gemini' : 'generated in demo mode'}</span>
                      <span><Check size={14} /> Budget independently calculated</span>
                      <span><Check size={14} /> {plan.timeline_notice ? 'Timeline reviewed' : 'Deadlines aligned to event date'}</span>
                    </div>
                  </article>

                  <article className="card budget-card">
                    <div className="section-heading">
                      <div><p className="eyebrow">PLAN WITH CLARITY</p><h2>Budget breakdown</h2></div>
                      <span className={`budget-badge ${plan.over_budget ? 'warning' : ''}`}>{plan.over_budget ? 'Over budget' : 'On track'}</span>
                    </div>
                    <p className="muted">Estimates are starting points. Add actual spending as you receive quotes.</p>
                    {plan.expenses.map((item) => {
                      const share = plan.event.budget > 0 ? Math.min(100, (item.estimated_amount / plan.event.budget) * 100) : 0
                      return (
                        <div className="expense-row" key={item.id}>
                          <div className="expense-info">
                            <div className="expense-title"><strong>{item.category}</strong><span>{item.item}</span></div>
                            <div className="expense-meter" aria-label={`${item.category}: ${share.toFixed(0)} percent of budget`}><span style={{ width: `${share}%` }} /></div>
                          </div>
                          <div className="expense-amount"><strong>{money(item.estimated_amount, plan.event.currency)}</strong><small>estimate</small></div>
                          <label className="quote-status"><span className="sr-only">Quotation status for {item.item}</span><select value={item.status} disabled={isPending(`status:${item.id}`)} onChange={(e) => void saveExpenseStatus(item.id, e.target.value as Expense['status'])}><option value="estimated">Estimated</option><option value="quoted">Quoted</option><option value="confirmed">Confirmed</option></select></label>
                          <label className="actual-input"><span className="sr-only">Actual spending for {item.item}</span><input type="number" min="0" step="1" placeholder="Actual" value={expenseDrafts[item.id] ?? (item.actual_amount === null ? '' : String(item.actual_amount))} onChange={(e) => setExpenseDrafts((current) => ({ ...current, [item.id]: e.target.value }))} /><button aria-label={`Save actual spending for ${item.item}`} disabled={isPending(`expense:${item.id}`)} onClick={() => void saveActual(item.id)}>Save</button></label>
                        </div>
                      )
                    })}
                    <div className="budget-total"><span>Estimated total <small>· {plan.event.currency}</small></span><strong>{money(plan.estimated_total, plan.event.currency)}</strong></div>
                    <p className="accessible-summary">Text summary: estimated expenses total {money(plan.estimated_total, plan.event.currency)} against a budget of {money(plan.event.budget, plan.event.currency)}. Actual spending entered so far is {money(plan.actual_total, plan.event.currency)}.</p>
                  </article>

                  <article className="card timeline-card">
                    <div className="section-heading"><div><p className="eyebrow">ONE STEP AT A TIME</p><h2>Preparation timeline</h2></div><span className="task-count">{plan.prep_tasks.filter((task) => task.completed).length}/{plan.prep_tasks.length}</span></div>
                    {plan.timeline_notice && <p className="timeline-notice">{plan.timeline_notice}</p>}
                    <div className="task-list">
                      {plan.prep_tasks.map((task) => (
                        <label className={`task-row ${task.completed ? 'is-done' : ''}`} key={task.id}>
                          <input type="checkbox" checked={task.completed} disabled={isPending(`task:${task.id}`)} onChange={(e) => void handleToggle('task', task.id, e.target.checked)} />
                          <span className="custom-check" aria-hidden="true">{task.completed && <Check size={13} />}</span>
                          <span className="task-text"><strong>{task.title}</strong><small>{task.deadline ? dateLabel(task.deadline) : 'Date to be decided'}</small></span>
                          <span className={`priority ${task.priority}`}>{task.priority}</span>
                        </label>
                      ))}
                    </div>
                  </article>

                  <article className="card vendor-card">
                    <div className="section-heading"><div><p className="eyebrow">PEOPLE WHO BRING IT TO LIFE</p><h2>Vendor checklist</h2></div><ClipboardCheck size={20} className="heading-icon" /></div>
                    <p className="muted">These are vendor categories to research, not verified providers.</p>
                    <div className="vendor-list">
                      {plan.vendors.map((vendor) => {
                        const draft = vendorDraft(vendor)
                        return (
                          <div className="vendor-item" key={vendor.id}>
                            <label className={`vendor-row ${vendor.completed ? 'is-done' : ''}`}>
                              <input type="checkbox" checked={vendor.completed} disabled={isPending(`vendor:${vendor.id}`)} onChange={(e) => void handleToggle('vendor', vendor.id, e.target.checked)} />
                              <span className="custom-check" aria-hidden="true">{vendor.completed && <Check size={13} />}</span>
                              <span><strong>{vendor.category}</strong><small>{vendor.requirement}</small></span>
                              <span className={`vendor-status ${vendor.status}`}>{vendor.status.replace('_', ' ')}</span>
                            </label>
                            <div className="vendor-fields">
                              <label><span>Vendor name</span><input maxLength={120} value={draft.vendor_name} onChange={(e) => updateVendorDraft(vendor, 'vendor_name', e.target.value)} placeholder="Optional" /></label>
                              <label><span>Contact</span><input maxLength={160} value={draft.contact} onChange={(e) => updateVendorDraft(vendor, 'contact', e.target.value)} placeholder="Optional" /></label>
                              <label><span>Quotation ({plan.event.currency})</span><input type="number" min="0" step="1" value={draft.quotation} onChange={(e) => updateVendorDraft(vendor, 'quotation', e.target.value)} placeholder="Optional" /></label>
                              <label><span>Booking status</span><select value={draft.status} onChange={(e) => updateVendorDraft(vendor, 'status', e.target.value as Vendor['status'])}><option value="to_research">To research</option><option value="contacted">Contacted</option><option value="quoted">Quoted</option><option value="booked">Booked</option></select></label>
                              <label className="vendor-notes"><span>Notes</span><input maxLength={500} value={draft.notes} onChange={(e) => updateVendorDraft(vendor, 'notes', e.target.value)} placeholder="Optional planning notes" /></label>
                              <button className="vendor-save" disabled={isPending(`vendor:${vendor.id}`)} onClick={() => void saveVendor(vendor)}>Save details</button>
                            </div>
                          </div>
                        )
                      })}
                    </div>
                  </article>

                  <article className="card schedule-card">
                    <div className="section-heading"><div><p className="eyebrow">THE DAY OF</p><h2>A simple event flow</h2></div><CalendarDays size={20} className="heading-icon" /></div>
                    <div className="schedule-list">{plan.schedule.map((item, index) => <div className="schedule-row" key={`${item.time}-${item.title}`}><span className="schedule-marker">{index + 1}</span><span className="schedule-time">{item.time}</span><span><strong>{item.title}</strong><small>{item.detail}</small></span></div>)}</div>
                  </article>

                  <article className="card ideas-card">
                    <div className="section-heading"><div><p className="eyebrow">THE LITTLE DETAILS</p><h2>Ideas with a reason</h2></div><Heart size={19} className="heading-icon" /></div>
                    <div className="ideas-list">{plan.ideas.map((idea) => <div className="idea-item" key={idea.title}><span className="idea-heart"><Heart size={16} /></span><div><h3>{idea.title}</h3><p>{idea.description}</p><small>{idea.rationale}</small>{idea.estimated_impact && <span className="impact-tag">{idea.estimated_impact}</span>}</div></div>)}</div>
                  </article>
                </div>

                <aside className="right-column">
                  <article className="refine-card">
                    <div className="refine-icon"><Sparkles size={20} /></div>
                    <p className="eyebrow">MAKE IT MORE YOU</p>
                    <h2>A little change?</h2>
                    <p>Ask for a budget adjustment, a new theme, or a different guest count. Your other choices stay in the plan.</p>
                    <form onSubmit={revisePlan} aria-busy={revisionLoading}>
                      <label className="sr-only" htmlFor="revision">What would you like to change?</label>
                      <textarea id="revision" rows={4} maxLength={1500} value={revision} onChange={(e) => setRevision(e.target.value)} placeholder="e.g. Reduce the budget to ₹30,000 and keep the food options vegetarian" />
                      <button className="primary-button full-button" type="submit" disabled={revisionLoading || revision.trim().length < 3}>
                        {revisionLoading ? <><LoaderCircle className="spin" size={16} /> Updating plan</> : <>Refine this plan <ArrowRight size={16} /></>}
                      </button>
                    </form>
                    <div className="prompt-suggestions">
                      <span>Try asking</span>
                      <button onClick={() => setRevision(`Reduce the budget to ${Math.max(1, Math.round(plan.event.budget * 0.8))}`)}>Reduce my budget</button>
                      <button onClick={() => setRevision('Make this plan simpler and more intimate')}>Make it simpler</button>
                    </div>
                  </article>

                  <article className="card savings-card">
                    <div className="section-heading"><div><p className="eyebrow">SPEND WITH INTENTION</p><h2>Save without losing the magic</h2></div></div>
                    <ul>{plan.savings.map((tip) => <li key={tip}><CircleCheck size={16} /> <span>{tip}</span></li>)}</ul>
                  </article>

                  <article className="card activity-card">
                    <div className="section-heading"><div><p className="eyebrow">HOW THIS PLAN WAS MADE</p><h2>Planning notes</h2></div></div>
                    <div className="activity-item"><span className="activity-check"><Check size={13} /></span><div><strong>{plan.ai_mode === 'live' ? 'Gemini plan generated' : 'Demo plan generated'}</strong><small>{plan.ai_mode === 'live' ? `Generated with ${health?.model ?? 'the configured Gemini model'} on the server` : 'Local deterministic planning; not GenAI'}</small></div></div>
                    <div className="activity-item"><span className="activity-check"><Check size={13} /></span><div><strong>Budget totals calculated</strong><small>Calculated from itemized expense estimates</small></div></div>
                    <div className="activity-item"><span className="activity-check"><Check size={13} /></span><div><strong>Timeline checked</strong><small>{plan.timeline_notice ?? 'Deadlines aligned to the event date'}</small></div></div>
                    {plan.assumptions.length > 0 && <div className="assumptions"><strong>Assumptions & notes</strong><ul>{plan.assumptions.map((item) => <li key={item}>{item}</li>)}</ul></div>}
                  </article>
                </aside>
              </div>
            </section>
          ) : (
            <section className="welcome">
              <div className="welcome-copy">
                <span className="welcome-kicker"><Sparkles size={15} /> YOUR CELEBRATION, THOUGHTFULLY PLANNED</span>
                <h1>Big moments,<br /><em>beautifully</em> planned.</h1>
                <p>From the first idea to the final checklist, bring your celebration together with a plan that fits your people, your date, and your budget.</p>
                <button className="primary-button welcome-button" onClick={startNewPlan}>Plan your celebration <ArrowRight size={17} /></button>
                <div className="welcome-trust"><span><Check size={14} /> Budget-aware</span><span><Check size={14} /> Made personal</span><span><Check size={14} /> Yours to refine</span></div>
              </div>
              <div className="welcome-art" aria-label="Illustration of a celebration invitation and flowers">
                <div className="art-sun" />
                <div className="art-leaf leaf-one" /><div className="art-leaf leaf-two" /><div className="art-leaf leaf-three" />
                <div className="art-card"><span>LET'S CELEBRATE</span><Heart size={31} /><strong>your<br />kind of<br />wonderful</strong><i>made with meaning</i></div>
                <div className="art-flower">✿</div><div className="art-sparkle">✦</div>
              </div>
              <div className="welcome-bottom">
                <div><span className="bottom-icon"><Coins size={18} /></span><span><strong>Thoughtful budgets</strong><small>Know where every estimate goes.</small></span></div>
                <div><span className="bottom-icon"><CalendarDays size={18} /></span><span><strong>A plan that has a date</strong><small>Turn the big day into small steps.</small></span></div>
                <div><span className="bottom-icon"><Heart size={18} /></span><span><strong>Made for your people</strong><small>Ideas shaped by what you tell us.</small></span></div>
              </div>
              <div className="welcome-footer">{health?.ai_mode === 'invalid' ? 'The server AI configuration is invalid. Live planning is unavailable until it is fixed.' : health?.ai_mode === 'live' && health.provider_configured ? `Gemini is configured for planning (${health.model ?? 'model set on the server'}).` : health?.ai_mode === 'live' ? 'Live mode needs a server-side Gemini API key before planning.' : 'Demo mode is active · add a Gemini API key on the server for live GenAI.'}</div>
            </section>
          )}
        </div>
        <footer className="page-footer"><span>Made for your moments, big and small.</span><span>Festiva AI · Plan with care</span></footer>
      </main>
    </div>
  )
}

export default App
