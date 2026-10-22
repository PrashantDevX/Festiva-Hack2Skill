import type { FormEvent } from 'react'
import {
  ArrowDownToLine,
  ArrowRight,
  CalendarDays,
  Check,
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
import { formatDate, formatMoney } from '../format'
import type { Expense, Plan, Vendor, VendorDraft } from '../types'
import { vendorDraftFor } from '../vendorDraft'

type VendorDraftChange = <Key extends keyof VendorDraft>(
  vendor: Vendor,
  field: Key,
  value: VendorDraft[Key],
) => void

type PlanWorkspaceProps = {
  plan: Plan
  revision: string
  revisionLoading: boolean
  expenseDrafts: Record<string, string>
  vendorDrafts: Record<string, VendorDraft>
  isPending: (key: string) => boolean
  onExport: () => void
  onStartNewPlan: () => void
  onRevisionChange: (value: string) => void
  onRevise: (event: FormEvent<HTMLFormElement>) => void
  onToggleTask: (id: string, completed: boolean) => void
  onToggleVendor: (id: string, completed: boolean) => void
  onExpenseDraftChange: (id: string, value: string) => void
  onSaveActual: (id: string) => void
  onExpenseStatusChange: (id: string, status: Expense['status']) => void
  onVendorDraftChange: VendorDraftChange
  onSaveVendor: (vendor: Vendor) => void
}

export function PlanWorkspace({
  plan,
  revision,
  revisionLoading,
  expenseDrafts,
  vendorDrafts,
  isPending,
  onExport,
  onStartNewPlan,
  onRevisionChange,
  onRevise,
  onToggleTask,
  onToggleVendor,
  onExpenseDraftChange,
  onSaveActual,
  onExpenseStatusChange,
  onVendorDraftChange,
  onSaveVendor,
}: PlanWorkspaceProps) {
  const completedTasks = plan.prep_tasks.filter((task) => task.completed).length
  const completion = plan.prep_tasks.length
    ? Math.round((completedTasks / plan.prep_tasks.length) * 100)
    : 0

  return (
    <section className="workspace">
      <div className="page-title-row workspace-title">
        <div>
          <p className="eyebrow">A LITTLE MORE JOY, A LOT LESS GUESSWORK</p>
          <h1>{plan.event.event_type}<span className="title-period">.</span></h1>
          <div className="event-meta">
            <span><CalendarDays size={15} /> {formatDate(plan.event.event_date)}</span>
            <span><MapPin size={15} /> {plan.event.location}</span>
            <span><Heart size={15} /> {plan.event.guest_count} guests</span>
          </div>
        </div>
        <div className="title-actions">
          <button className="secondary-button" onClick={onExport}><ArrowDownToLine size={16} /> Export plan</button>
          <button className="primary-button compact" onClick={onStartNewPlan}><Plus size={17} /> New event</button>
        </div>
      </div>

      {plan.ai_mode === 'demo' && (
        <div className="demo-banner"><Sparkles size={17} /><span><strong>Demo-generated plan</strong> - local planning logic was used. Live AI is not active. Estimates are not vendor quotes.</span></div>
      )}

      <StatsGrid plan={plan} completion={completion} completedTasks={completedTasks} />

      <div className="two-column">
        <div className="main-column">
          <OverviewCard plan={plan} />
          <BudgetCard
            plan={plan}
            expenseDrafts={expenseDrafts}
            isPending={isPending}
            onDraftChange={onExpenseDraftChange}
            onSaveActual={onSaveActual}
            onStatusChange={onExpenseStatusChange}
          />
          <TimelineCard
            plan={plan}
            completedTasks={completedTasks}
            isPending={isPending}
            onToggle={onToggleTask}
          />
          <VendorCard
            plan={plan}
            vendorDrafts={vendorDrafts}
            isPending={isPending}
            onToggle={onToggleVendor}
            onDraftChange={onVendorDraftChange}
            onSaveVendor={onSaveVendor}
          />
          <ScheduleCard plan={plan} />
          <IdeasCard plan={plan} />
        </div>

        <aside className="right-column">
          <RefineCard
            plan={plan}
            revision={revision}
            revisionLoading={revisionLoading}
            onRevisionChange={onRevisionChange}
            onRevise={onRevise}
          />
          <SavingsCard plan={plan} />
          <ActivityCard plan={plan} />
        </aside>
      </div>
    </section>
  )
}

type StatsGridProps = {
  plan: Plan
  completion: number
  completedTasks: number
}

function StatsGrid({ plan, completion, completedTasks }: StatsGridProps) {
  return (
    <div className="stats-grid">
      <article className="stat-card budget-stat">
        <div className="stat-top"><span>Total budget</span><span className="stat-icon"><Coins size={17} /></span></div>
        <strong>{formatMoney(plan.event.budget, plan.event.currency)}</strong>
        <small>{plan.event.guest_count} guests · planning limit</small>
      </article>
      <article className="stat-card">
        <div className="stat-top"><span>Estimated spend</span><span className="stat-icon"><Flower2 size={17} /></span></div>
        <strong>{formatMoney(plan.estimated_total, plan.event.currency)}</strong>
        <small>{plan.over_budget ? 'Over budget — review estimates and actuals' : `${formatMoney(plan.remaining_budget, plan.event.currency)} estimated remaining`}</small>
      </article>
      <article className="stat-card">
        <div className="stat-top"><span>Actual spend</span><span className="stat-icon"><Coins size={17} /></span></div>
        <strong>{formatMoney(plan.actual_total, plan.event.currency)}</strong>
        <small>Update as real costs come in</small>
      </article>
      <article className="stat-card progress-stat">
        <div className="stat-top"><span>Planning progress</span><span className="stat-icon"><ClipboardCheck size={17} /></span></div>
        <strong>{completion}%</strong>
        <div className="progress-track" role="progressbar" aria-label="Preparation tasks complete" aria-valuenow={completion} aria-valuemin={0} aria-valuemax={100}><span style={{ width: `${completion}%` }} /></div>
        <small>{completedTasks} of {plan.prep_tasks.length} tasks done</small>
      </article>
    </div>
  )
}

function OverviewCard({ plan }: { plan: Plan }) {
  return (
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
        <span><Check size={14} /> Plan {plan.ai_mode === 'live' ? 'generated with live AI' : 'generated in demo mode'}</span>
        <span><Check size={14} /> Budget independently calculated</span>
        <span><Check size={14} /> {plan.timeline_notice ? 'Timeline reviewed' : 'Deadlines aligned to event date'}</span>
      </div>
    </article>
  )
}

type BudgetCardProps = {
  plan: Plan
  expenseDrafts: Record<string, string>
  isPending: (key: string) => boolean
  onDraftChange: (id: string, value: string) => void
  onSaveActual: (id: string) => void
  onStatusChange: (id: string, status: Expense['status']) => void
}

function BudgetCard({
  plan,
  expenseDrafts,
  isPending,
  onDraftChange,
  onSaveActual,
  onStatusChange,
}: BudgetCardProps) {
  return (
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
              <div className="expense-meter" role="progressbar" aria-label={`${item.category}: ${share.toFixed(0)} percent of budget`} aria-valuenow={Math.round(share)} aria-valuemin={0} aria-valuemax={100}><span style={{ width: `${share}%` }} /></div>
            </div>
            <div className="expense-amount"><strong>{formatMoney(item.estimated_amount, plan.event.currency)}</strong><small>estimate</small></div>
            <label className="quote-status"><span className="sr-only">Quotation status for {item.item}</span><select value={item.status} disabled={isPending(`status:${item.id}`)} onChange={(e) => onStatusChange(item.id, e.target.value as Expense['status'])}><option value="estimated">Estimated</option><option value="quoted">Quoted</option><option value="confirmed">Confirmed</option></select></label>
            <label className="actual-input"><span className="sr-only">Actual spending for {item.item}</span><input type="number" min="0" step="1" placeholder="Actual" value={expenseDrafts[item.id] ?? (item.actual_amount === null ? '' : String(item.actual_amount))} onChange={(e) => onDraftChange(item.id, e.target.value)} /><button aria-label={`Save actual spending for ${item.item}`} disabled={isPending(`expense:${item.id}`)} onClick={() => onSaveActual(item.id)}>Save</button></label>
          </div>
        )
      })}
      <div className="budget-total"><span>Estimated total <small>· {plan.event.currency}</small></span><strong>{formatMoney(plan.estimated_total, plan.event.currency)}</strong></div>
      <p className="accessible-summary">Text summary: estimated expenses total {formatMoney(plan.estimated_total, plan.event.currency)} against a budget of {formatMoney(plan.event.budget, plan.event.currency)}. Actual spending entered so far is {formatMoney(plan.actual_total, plan.event.currency)}.</p>
    </article>
  )
}

type TimelineCardProps = {
  plan: Plan
  completedTasks: number
  isPending: (key: string) => boolean
  onToggle: (id: string, completed: boolean) => void
}

function TimelineCard({ plan, completedTasks, isPending, onToggle }: TimelineCardProps) {
  return (
    <article className="card timeline-card">
      <div className="section-heading"><div><p className="eyebrow">ONE STEP AT A TIME</p><h2>Preparation timeline</h2></div><span className="task-count">{completedTasks}/{plan.prep_tasks.length}</span></div>
      {plan.timeline_notice && <p className="timeline-notice">{plan.timeline_notice}</p>}
      <div className="task-list">
        {plan.prep_tasks.map((task) => (
          <label className={`task-row ${task.completed ? 'is-done' : ''}`} key={task.id}>
            <input type="checkbox" checked={task.completed} disabled={isPending(`task:${task.id}`)} onChange={(e) => onToggle(task.id, e.target.checked)} />
            <span className="custom-check" aria-hidden="true">{task.completed && <Check size={13} />}</span>
            <span className="task-text"><strong>{task.title}</strong><small>{task.deadline ? formatDate(task.deadline) : 'Date to be decided'}</small></span>
            <span className={`priority ${task.priority}`}>{task.priority}</span>
          </label>
        ))}
      </div>
    </article>
  )
}

type VendorCardProps = {
  plan: Plan
  vendorDrafts: Record<string, VendorDraft>
  isPending: (key: string) => boolean
  onToggle: (id: string, completed: boolean) => void
  onDraftChange: VendorDraftChange
  onSaveVendor: (vendor: Vendor) => void
}

function VendorCard({
  plan,
  vendorDrafts,
  isPending,
  onToggle,
  onDraftChange,
  onSaveVendor,
}: VendorCardProps) {
  return (
    <article className="card vendor-card">
      <div className="section-heading"><div><p className="eyebrow">PEOPLE WHO BRING IT TO LIFE</p><h2>Vendor checklist</h2></div><ClipboardCheck size={20} className="heading-icon" /></div>
      <p className="muted">These are vendor categories to research, not verified providers.</p>
      <div className="vendor-list">
        {plan.vendors.map((vendor) => {
          const draft = vendorDraftFor(vendor, vendorDrafts)
          return (
            <div className="vendor-item" key={vendor.id}>
              <label className={`vendor-row ${vendor.completed ? 'is-done' : ''}`}>
                <input type="checkbox" checked={vendor.completed} disabled={isPending(`vendor:${vendor.id}`)} onChange={(e) => onToggle(vendor.id, e.target.checked)} />
                <span className="custom-check" aria-hidden="true">{vendor.completed && <Check size={13} />}</span>
                <span><strong>{vendor.category}</strong><small>{vendor.requirement}</small></span>
                <span className={`vendor-status ${vendor.status}`}>{vendor.status.replace('_', ' ')}</span>
              </label>
              <div className="vendor-fields">
                <label><span>Vendor name</span><input maxLength={120} value={draft.vendor_name} onChange={(e) => onDraftChange(vendor, 'vendor_name', e.target.value)} placeholder="Optional" /></label>
                <label><span>Contact</span><input maxLength={160} value={draft.contact} onChange={(e) => onDraftChange(vendor, 'contact', e.target.value)} placeholder="Optional" /></label>
                <label><span>Quotation ({plan.event.currency})</span><input type="number" min="0" step="1" value={draft.quotation} onChange={(e) => onDraftChange(vendor, 'quotation', e.target.value)} placeholder="Optional" /></label>
                <label><span>Booking status</span><select value={draft.status} onChange={(e) => onDraftChange(vendor, 'status', e.target.value as Vendor['status'])}><option value="to_research">To research</option><option value="contacted">Contacted</option><option value="quoted">Quoted</option><option value="booked">Booked</option></select></label>
                <label className="vendor-notes"><span>Notes</span><input maxLength={500} value={draft.notes} onChange={(e) => onDraftChange(vendor, 'notes', e.target.value)} placeholder="Optional planning notes" /></label>
                <button className="vendor-save" disabled={isPending(`vendor:${vendor.id}`)} onClick={() => onSaveVendor(vendor)}>Save details</button>
              </div>
            </div>
          )
        })}
      </div>
    </article>
  )
}

function ScheduleCard({ plan }: { plan: Plan }) {
  return (
    <article className="card schedule-card">
      <div className="section-heading"><div><p className="eyebrow">THE DAY OF</p><h2>A simple event flow</h2></div><CalendarDays size={20} className="heading-icon" /></div>
      <div className="schedule-list">{plan.schedule.map((item, index) => <div className="schedule-row" key={`${item.time}-${item.title}`}><span className="schedule-marker">{index + 1}</span><span className="schedule-time">{item.time}</span><span><strong>{item.title}</strong><small>{item.detail}</small></span></div>)}</div>
    </article>
  )
}

function IdeasCard({ plan }: { plan: Plan }) {
  return (
    <article className="card ideas-card">
      <div className="section-heading"><div><p className="eyebrow">THE LITTLE DETAILS</p><h2>Ideas with a reason</h2></div><Heart size={19} className="heading-icon" /></div>
      <div className="ideas-list">{plan.ideas.map((idea) => <div className="idea-item" key={idea.title}><span className="idea-heart"><Heart size={16} /></span><div><h3>{idea.title}</h3><p>{idea.description}</p><small>{idea.rationale}</small>{idea.estimated_impact && <span className="impact-tag">{idea.estimated_impact}</span>}</div></div>)}</div>
    </article>
  )
}

type RefineCardProps = {
  plan: Plan
  revision: string
  revisionLoading: boolean
  onRevisionChange: (value: string) => void
  onRevise: (event: FormEvent<HTMLFormElement>) => void
}

function RefineCard({
  plan,
  revision,
  revisionLoading,
  onRevisionChange,
  onRevise,
}: RefineCardProps) {
  return (
    <article className="refine-card">
      <div className="refine-icon"><Sparkles size={20} /></div>
      <p className="eyebrow">MAKE IT MORE YOU</p>
      <h2>A little change?</h2>
      <p>Ask for a budget adjustment, a new theme, or a different guest count. Your other choices stay in the plan.</p>
      <form onSubmit={onRevise} aria-busy={revisionLoading}>
        <label className="sr-only" htmlFor="revision">What would you like to change?</label>
        <textarea id="revision" rows={4} maxLength={1500} value={revision} onChange={(e) => onRevisionChange(e.target.value)} placeholder="e.g. Reduce the budget to ₹30,000 and keep the food options vegetarian" />
        <button className="primary-button full-button" type="submit" disabled={revisionLoading || revision.trim().length < 3}>
          {revisionLoading ? <><LoaderCircle className="spin" size={16} /> Updating plan</> : <>Refine this plan <ArrowRight size={16} /></>}
        </button>
      </form>
      <div className="prompt-suggestions">
        <span>Try asking</span>
        <button onClick={() => onRevisionChange(`Reduce the budget to ${Math.max(1, Math.round(plan.event.budget * 0.8))}`)}>Reduce my budget</button>
        <button onClick={() => onRevisionChange('Make this plan simpler and more intimate')}>Make it simpler</button>
      </div>
    </article>
  )
}

function SavingsCard({ plan }: { plan: Plan }) {
  return (
    <article className="card savings-card">
      <div className="section-heading"><div><p className="eyebrow">SPEND WITH INTENTION</p><h2>Save without losing the magic</h2></div></div>
      <ul>{plan.savings.map((tip) => <li key={tip}><CircleCheck size={16} /> <span>{tip}</span></li>)}</ul>
    </article>
  )
}

function ActivityCard({ plan }: { plan: Plan }) {
  return (
    <article className="card activity-card">
      <div className="section-heading"><div><p className="eyebrow">HOW THIS PLAN WAS MADE</p><h2>Planning notes</h2></div></div>
      <div className="activity-item"><span className="activity-check"><Check size={13} /></span><div><strong>{plan.ai_mode === 'live' ? 'Live AI plan generated' : 'Demo plan generated'}</strong><small>{plan.ai_mode === 'live' ? 'Generated by live AI on the server' : 'Local deterministic planning; no live AI'}</small></div></div>
      <div className="activity-item"><span className="activity-check"><Check size={13} /></span><div><strong>Budget totals calculated</strong><small>Calculated from itemized expense estimates</small></div></div>
      <div className="activity-item"><span className="activity-check"><Check size={13} /></span><div><strong>Timeline checked</strong><small>{plan.timeline_notice ?? 'Deadlines aligned to the event date'}</small></div></div>
      {plan.assumptions.length > 0 && <div className="assumptions"><strong>Assumptions & notes</strong><ul>{plan.assumptions.map((item) => <li key={item}>{item}</li>)}</ul></div>}
    </article>
  )
}
