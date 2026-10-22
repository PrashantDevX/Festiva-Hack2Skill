import { ChevronDown, Flower2, Plus, Sparkles } from 'lucide-react'
import type { Plan } from '../types'

type SidebarProps = {
  plans: Plan[]
  selectedPlanId: string | null
  showCreate: boolean
  onShowWorkspace: () => void
  onStartNewPlan: () => void
  onSelectPlan: (id: string) => void
}

export function Sidebar({
  plans,
  selectedPlanId,
  showCreate,
  onShowWorkspace,
  onStartNewPlan,
  onSelectPlan,
}: SidebarProps) {
  return (
    <aside className="sidebar">
      <a
        className="brand"
        href="#main-content"
        aria-label="Festiva AI workspace"
        onClick={onShowWorkspace}
      >
        <span className="brand-mark"><Flower2 size={21} strokeWidth={1.8} /></span>
        <span>festiva<span className="brand-ai">.ai</span></span>
      </a>
      <p className="side-label">YOUR PLANNER</p>
      <button className={`side-link ${!showCreate ? 'active' : ''}`} onClick={onShowWorkspace}>
        <Sparkles size={17} /> Workspace
      </button>
      <button className="side-link" onClick={onStartNewPlan}>
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
            className={`saved-event ${selectedPlanId === saved.id && !showCreate ? 'selected' : ''}`}
            key={saved.id}
            aria-current={selectedPlanId === saved.id && !showCreate ? 'page' : undefined}
            onClick={() => onSelectPlan(saved.id)}
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
        <span><strong>Your space</strong><small>Private to this browser</small></span>
      </div>
    </aside>
  )
}
