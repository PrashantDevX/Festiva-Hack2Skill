import { useEffect, useRef, useState, type FormEvent } from 'react'
import { CircleCheck } from 'lucide-react'
import { api } from './api'
import { getErrorMessage } from './format'
import { applyVendorDraft, vendorDraftFor } from './vendorDraft'
import { CreatePlanView } from './components/CreatePlanView'
import { PlanWorkspace } from './components/PlanWorkspace'
import { Sidebar } from './components/Sidebar'
import { Topbar } from './components/Topbar'
import { WelcomeView } from './components/WelcomeView'
import type { EventInput, Health, Plan, Vendor, VendorDraft } from './types'

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
    let cancelled = false

    const bootstrap = async () => {
      try {
        // Health first, then the private plan list. This guarantees the first
        // anonymous session cookie is established before plan requests race.
        const service = await api.health()
        if (cancelled) return
        setHealth(service)
        const saved = await api.listPlans()
        if (cancelled) return
        setPlans(saved)
        if (saved.length) setPlan(saved[0])
      } catch (reason) {
        if (!cancelled) {
          setError(getErrorMessage(reason, 'Could not load your workspace.'))
        }
      }
    }

    void bootstrap()
    return () => {
      cancelled = true
    }
  }, [])

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
      setError(getErrorMessage(reason, 'Could not generate your plan.'))
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
      setError(getErrorMessage(reason, 'The revision could not be applied.'))
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
      setError(getErrorMessage(reason, 'Could not save this checklist update.'))
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
      setError(getErrorMessage(reason, 'Could not save actual spending.'))
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
      setError(getErrorMessage(reason, 'Could not update quotation status.'))
    } finally {
      endRequest(`status:${expenseId}`)
    }
  }

  const updateVendorDraft = <Key extends keyof VendorDraft>(
    vendor: Vendor,
    field: Key,
    value: VendorDraft[Key],
  ) => {
    setVendorDrafts((current) => applyVendorDraft(current, vendor, field, value))
  }

  const saveVendor = async (vendor: Vendor) => {
    if (!plan) return
    const draft = vendorDraftFor(vendor, vendorDrafts)
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
      setError(getErrorMessage(reason, 'Could not save vendor details.'))
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
      setError(getErrorMessage(reason, 'Could not open this saved plan.'))
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
      <Sidebar
        plans={plans}
        selectedPlanId={plan?.id ?? null}
        showCreate={showCreate}
        onShowWorkspace={() => setShowCreate(false)}
        onStartNewPlan={startNewPlan}
        onSelectPlan={(id) => void selectPlan(id)}
      />

      <main className="main-area" id="main-content" tabIndex={-1}>
        <Topbar showCreate={showCreate} plan={plan} health={health} />

        <div className="content-wrap">
          <div className="sr-only" role="status" aria-live="polite">
            {loading ? 'Building your plan.' : revisionLoading ? 'Updating your plan.' : ''}
          </div>
          {error && showError(error)}
          {notice && <p className="alert success" role="status"><CircleCheck size={17} /> {notice}</p>}

          {showCreate ? (
            <CreatePlanView
              event={event}
              health={health}
              loading={loading}
              onChange={updateEvent}
              onSubmit={createPlan}
              onBack={() => setShowCreate(false)}
            />
          ) : plan ? (
            <PlanWorkspace
              plan={plan}
              revision={revision}
              revisionLoading={revisionLoading}
              expenseDrafts={expenseDrafts}
              vendorDrafts={vendorDrafts}
              isPending={isPending}
              onExport={exportPlan}
              onStartNewPlan={startNewPlan}
              onRevisionChange={setRevision}
              onRevise={revisePlan}
              onToggleTask={(id, completed) => void handleToggle('task', id, completed)}
              onToggleVendor={(id, completed) => void handleToggle('vendor', id, completed)}
              onExpenseDraftChange={(id, value) => setExpenseDrafts((current) => ({ ...current, [id]: value }))}
              onSaveActual={(id) => void saveActual(id)}
              onExpenseStatusChange={(id, status) => void saveExpenseStatus(id, status)}
              onVendorDraftChange={updateVendorDraft}
              onSaveVendor={(vendor) => void saveVendor(vendor)}
            />
          ) : (
            <WelcomeView health={health} onStartNewPlan={startNewPlan} />
          )}
        </div>
        <footer className="page-footer"><span>Made for your moments, big and small.</span><span>Festiva AI · Plan with care</span></footer>
      </main>
    </div>
  )
}

export default App
