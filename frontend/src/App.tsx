import { useState } from 'react'
import { Menu, RefreshCw, AlertCircle } from 'lucide-react'
import { Sidebar } from './components/Sidebar'
import { CaseQueue } from './components/CaseQueue'
import { CaseDetails } from './components/CaseDetails'
import { Overview } from './pages/Overview'
import { Investigate } from './pages/Investigate'
import { useSparkov } from './hooks/useSparkov'
import type { PaymentInput } from './sparkovTypes'

export type AnalystPage = 'overview' | 'queue' | 'investigate'
export default function App() {
  const deepLink = /^SPINV_[a-f0-9]{32}$/.test(new URLSearchParams(window.location.search).get('investigation') ?? '')
  const [page, setPage] = useState<AnalystPage>(deepLink ? 'queue' : 'overview')
  const [caseOpen, setCaseOpen] = useState(deepLink)
  const [queueFilter, setQueueFilter] = useState('all')
  const [menuOpen, setMenuOpen] = useState(false)
  const workspace = useSparkov()
  function navigate(next: AnalystPage) { setPage(next); setCaseOpen(false); setMenuOpen(false); window.history.replaceState(null, '', window.location.pathname) }
  function queue(filter: string) { setQueueFilter(filter); navigate('queue') }
  function open(id: string) { setPage('queue'); setCaseOpen(true); window.history.replaceState(null, '', `?investigation=${encodeURIComponent(id)}`); void workspace.open(id); window.scrollTo({ top: 0, behavior: 'smooth' }) }
  async function submit(payment: PaymentInput) { const id = await workspace.start(payment); if (id) { setPage('queue'); setCaseOpen(true); window.history.replaceState(null, '', `?investigation=${id}`); window.scrollTo({ top: 0, behavior: 'smooth' }) } }
  const title = page === 'overview' ? 'Overview' : page === 'investigate' ? 'Investigate payment' : caseOpen ? 'Case review' : 'Review queue'
  return <div className="workspace-shell"><Sidebar page={page} onPage={navigate} open={menuOpen} onClose={() => setMenuOpen(false)} /><div className="workspace-content"><header className="workspace-topbar"><div><button className="round-button mobile-menu" aria-label="Open navigation" onClick={() => setMenuOpen(true)}><Menu size={21} /></button><span className="breadcrumb-label">Workspace</span><span className="breadcrumb-divider">/</span><strong>{title}</strong></div><div><span className={`workspace-status ${workspace.error ? 'unavailable' : ''}`}><i />{workspace.error ? 'Connection needs attention' : workspace.loading ? 'Connecting…' : 'Workspace ready'}</span><button className="round-button" aria-label="Refresh workspace" title="Refresh workspace" disabled={workspace.loading} onClick={() => void workspace.refresh()}><RefreshCw size={18} className={workspace.loading ? 'spin' : ''} /></button><span className="analyst-avatar" aria-label="Analyst workspace">FS</span></div></header>
    <main className="workspace-main">{workspace.error && <div className="error-banner" role="alert"><AlertCircle size={20} /><p>{workspace.error}</p><button onClick={() => void workspace.refresh()}>Try again</button></div>}
      {!workspace.options ? <section className="card empty-state"><ShieldPlaceholder /><h2>{workspace.loading ? 'Preparing your workspace…' : 'Workspace is unavailable'}</h2><p>{workspace.loading ? 'Loading saved cases and payment history.' : 'Restore the local service, then try again. Your saved cases have not been removed.'}</p></section> : page === 'overview' ? <Overview rows={workspace.rows} onOpen={open} onQueue={queue} onNew={() => navigate('investigate')} /> : page === 'investigate' ? <Investigate options={workspace.options} busy={workspace.busy} onSubmit={submit} /> : caseOpen ? workspace.focused ? <CaseDetails key={workspace.focused.investigation_id} row={workspace.focused} onReview={workspace.review} onBack={() => navigate('queue')} /> : <section className="card empty-state"><h2>Opening case…</h2><p>Please wait while the saved assessment is retrieved.</p><button className="text-button" onClick={() => navigate('queue')}>Back to review queue</button></section> : <><div className="page-intro"><div><div className="eyebrow">CASE MANAGEMENT</div><h1>Review queue</h1><p>Prioritize payments, inspect the evidence and record your decision.</p></div><button className="primary-button" onClick={() => navigate('investigate')}>Investigate payment</button></div><CaseQueue key={queueFilter} initialFilter={queueFilter} rows={workspace.rows} onOpen={open} onDelete={workspace.remove} /></>}
      <footer className="workspace-footer"><span>FinSentry AI · Analyst workspace</span><span>{workspace.lastUpdated ? `Cases updated ${workspace.lastUpdated.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}` : 'Connecting'} · Refreshes every 20 seconds</span></footer>
    </main></div></div>
}
function ShieldPlaceholder() { return <div className="loading-symbol">FS</div> }
