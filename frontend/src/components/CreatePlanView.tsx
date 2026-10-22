import type { FormEvent } from 'react'
import { ArrowRight, LoaderCircle, Sparkles } from 'lucide-react'
import { getAiReadiness, getCreationNotice } from '../aiStatus'
import type { EventInput, Health } from '../types'

type CreatePlanViewProps = {
  event: EventInput
  health: Health | null
  loading: boolean
  onChange: (field: keyof EventInput, value: string | number | null) => void
  onSubmit: (event: FormEvent<HTMLFormElement>) => void
  onBack: () => void
}

export function CreatePlanView({
  event,
  health,
  loading,
  onChange,
  onSubmit,
  onBack,
}: CreatePlanViewProps) {
  const notice = getCreationNotice(getAiReadiness(health))

  return (
    <section className="create-page">
      <button className="back-link" onClick={onBack}>← Back to workspace</button>
      <div className="page-title-row">
        <div>
          <p className="eyebrow">LET'S MAKE IT MEANINGFUL</p>
          <h1>Tell us what you're celebrating.</h1>
          <p className="subtitle">A few details help shape a plan that feels like yours.</p>
        </div>
        <div className="title-icon"><Sparkles size={25} /></div>
      </div>
      <form className="event-form card" onSubmit={onSubmit} aria-busy={loading}>
        <div className="form-section-heading"><span>01</span><div><h2>The occasion</h2><p>Start with the details you already know.</p></div></div>
        <label className="field full">
          <span>Describe your event <b>*</b></span>
          <textarea
            required
            minLength={10}
            maxLength={4000}
            value={event.description}
            onChange={(e) => onChange('description', e.target.value)}
            placeholder="A relaxed birthday dinner for my parents, with a garden setting and close family..."
            rows={3}
          />
          <small>Include any details that matter to you. Don't include sensitive personal information.</small>
        </label>
        <div className="form-grid">
          <label className="field">
            <span>Celebration type <b>*</b></span>
            <select value={event.event_type} onChange={(e) => onChange('event_type', e.target.value)}>
              {['Wedding', 'Birthday', 'Anniversary', 'College event', 'Community celebration', 'Other'].map((item) => <option key={item}>{item}</option>)}
            </select>
          </label>
          <label className="field">
            <span>Event date</span>
            <input type="date" value={event.event_date ?? ''} onChange={(e) => onChange('event_date', e.target.value || null)} />
            <small>Leave blank if undecided; deadlines will be added once known.</small>
          </label>
          <label className="field">
            <span>Location <b>*</b></span>
            <input required minLength={2} maxLength={160} value={event.location} onChange={(e) => onChange('location', e.target.value)} placeholder="City or venue area" />
          </label>
          <label className="field">
            <span>Guest count <b>*</b></span>
            <input required type="number" min="1" max="100000" value={event.guest_count} onChange={(e) => onChange('guest_count', Number(e.target.value))} />
          </label>
        </div>
        <div className="form-section-heading budget-heading"><span>02</span><div><h2>Make it work for you</h2><p>Budgets are estimates until you confirm real quotations.</p></div></div>
        <div className="form-grid">
          <div className="field">
            <span id="budget-label">Total budget <b>*</b></span>
            <div className="input-combo">
              <select aria-label="Currency" value={event.currency} onChange={(e) => onChange('currency', e.target.value)}>
                <option value="INR">INR ₹</option><option value="USD">USD $</option><option value="EUR">EUR €</option><option value="GBP">GBP £</option>
              </select>
              <input aria-labelledby="budget-label" required type="number" min="1" step="1" max="100000000" value={event.budget} onChange={(e) => onChange('budget', Number(e.target.value))} />
            </div>
          </div>
          <label className="field">
            <span>Food & dietary needs</span>
            <input maxLength={500} value={event.dietary_needs} onChange={(e) => onChange('dietary_needs', e.target.value)} placeholder="e.g. vegetarian, nut-free options" />
          </label>
          <label className="field full">
            <span>Your style & preferences</span>
            <textarea rows={2} maxLength={1500} value={event.preferences} onChange={(e) => onChange('preferences', e.target.value)} placeholder="Themes, colors, cultural preferences, atmosphere..." />
          </label>
          <label className="field full">
            <span>Special requirements</span>
            <textarea rows={2} maxLength={1000} value={event.special_requirements} onChange={(e) => onChange('special_requirements', e.target.value)} placeholder="Accessibility, timing, or other constraints" />
          </label>
        </div>
        <div className="form-actions">
          <p><Sparkles size={16} /> {notice}</p>
          <button className="primary-button" type="submit" disabled={loading}>
            {loading ? <><LoaderCircle className="spin" size={17} /> Building your plan</> : <>Create my plan <ArrowRight size={17} /></>}
          </button>
        </div>
      </form>
    </section>
  )
}
