import { ArrowRight, CalendarDays, Check, Coins, Heart, Sparkles } from 'lucide-react'
import { getAiReadiness, getWelcomeNotice } from '../aiStatus'
import type { Health } from '../types'

type WelcomeViewProps = {
  health: Health | null
  onStartNewPlan: () => void
}

export function WelcomeView({ health, onStartNewPlan }: WelcomeViewProps) {
  const notice = getWelcomeNotice(getAiReadiness(health))

  return (
    <section className="welcome">
      <div className="welcome-copy">
        <span className="welcome-kicker"><Sparkles size={15} /> YOUR CELEBRATION, THOUGHTFULLY PLANNED</span>
        <h1>Big moments,<br /><em>beautifully</em> planned.</h1>
        <p>From the first idea to the final checklist, bring your celebration together with a plan that fits your people, your date, and your budget.</p>
        <button className="primary-button welcome-button" onClick={onStartNewPlan}>Plan your celebration <ArrowRight size={17} /></button>
        <div className="welcome-trust"><span><Check size={14} /> Budget-aware</span><span><Check size={14} /> Made personal</span><span><Check size={14} /> Yours to refine</span></div>
      </div>
      <div className="welcome-art" role="img" aria-label="Illustration of a celebration invitation and flowers">
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
      <div className="welcome-footer">{notice}</div>
    </section>
  )
}
