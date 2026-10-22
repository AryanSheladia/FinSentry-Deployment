import { ArrowRight, ClipboardList, AlertTriangle, ShieldCheck, Files } from 'lucide-react'
import type { SparkovInvestigation } from '../sparkovTypes'
import { needsAttention, isUrgent, latestReview } from '../services/analyst'
import { CaseQueue } from '../components/CaseQueue'

export function Overview({ rows, onOpen, onQueue, onNew }: { rows: SparkovInvestigation[]; onOpen: (id: string) => void; onQueue: (filter: string) => void; onNew: () => void }) {
  const cards = [
    { label: 'Recent cases', value: rows.length, note: 'Latest 100 submitted payments', icon: Files, filter: 'all' },
    { label: 'Needs attention', value: rows.filter(needsAttention).length, note: 'Pending review or follow-up', icon: ClipboardList, filter: 'attention' },
    { label: 'Escalations', value: rows.filter(isUrgent).length, note: 'Human or senior review needed', icon: AlertTriangle, filter: 'urgent' },
    { label: 'Cleared by an analyst', value: rows.filter(r => latestReview(r)?.action === 'CLEAR').length, note: 'Decision recorded after review', icon: ShieldCheck, filter: 'cleared' },
  ]
  return <><div className="page-intro"><div><div className="eyebrow">FRAUD OPERATIONS</div><h1>Your review workspace</h1><p>See what needs attention and make an informed decision on each payment.</p></div><button className="primary-button" onClick={onNew}>Investigate payment<ArrowRight size={17} /></button></div><div className="metric-grid">{cards.map(({ label, value, note, icon: Icon, filter }) => <button className="metric-card" key={label} onClick={() => onQueue(filter)}><span>{label}<Icon size={19} /></span><strong>{value}</strong><small>{note}</small></button>)}</div>
    <CaseQueue rows={rows} onOpen={onOpen} compact /><div className="overview-bottom"><section className="card guidance-card"><h2>A simple review flow</h2><ol><li><strong>Open a case</strong><p>Start with cases awaiting human review or further investigation.</p></li><li><strong>Check the reasons</strong><p>Compare unusual spending, timing and location with customer history.</p></li><li><strong>Record your decision</strong><p>Clear the case, request more investigation or escalate it with notes.</p></li></ol><button className="text-button" onClick={() => onQueue('attention')}>Go to review queue<ArrowRight size={15} /></button></section><section className="card guidance-card"><h2>Understand the assessment</h2><p><strong>Risk indicator</strong> is the model’s estimate for this simulated payment. It is not proof of fraud.</p><p><strong>Information available</strong> tells you whether there is enough customer history and supporting evidence to assess the payment.</p><p><strong>Your review decision</strong> is saved separately. This workspace does not block payments or move money.</p><div className="simulation-note">Training workspace · Simulated card-payment data · No live bank connection</div></section></div></>
}
