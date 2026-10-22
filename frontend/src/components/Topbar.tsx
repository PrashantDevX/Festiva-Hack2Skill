import { getAiReadiness, getAiStatusLabel } from '../aiStatus'
import type { Health, Plan } from '../types'

type TopbarProps = {
  showCreate: boolean
  plan: Plan | null
  health: Health | null
}

export function Topbar({ showCreate, plan, health }: TopbarProps) {
  const readiness = getAiReadiness(health)

  return (
    <header className="topbar">
      <div className="breadcrumb">Your workspace <span>/</span> {showCreate ? 'New event' : plan?.event.event_type ?? 'Overview'}</div>
      <div className={`ai-indicator ${readiness === 'live' ? 'live' : ''}`}>
        <span className="status-dot" />
        {getAiStatusLabel(readiness)}
      </div>
    </header>
  )
}
